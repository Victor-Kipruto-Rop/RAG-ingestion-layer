"""User API-key management. Requires a trusted PesaGuard-issued HS256 access token.
The dashboard must never receive the datasource's internal REGISTRY_API_KEYS secret.
"""
import hashlib, secrets, uuid
from datetime import timedelta

import jwt
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db, SessionLocal
from .models import ApiKey, ApiKeyAuditEvent, DeveloperAccount, DeveloperWorkspace, DeveloperSession, DeveloperWebhook
from .email_service import send_transactional_email
import logging

router = APIRouter(prefix="/api/v1/keys", tags=["API key management"])

def _trusted_identity_signing_keys() -> tuple[dict[str, str], str]:
    """Load the same rotating HS256 key ring used by PesaGuard's auth_rbac provider."""
    import json
    active_kid = (settings.api_key_auth_jwt_active_kid or "current").strip()
    raw_ring = (settings.api_key_auth_jwt_keys_json or "").strip()
    if raw_ring:
        try:
            ring = json.loads(raw_ring)
        except json.JSONDecodeError:
            raise HTTPException(503, "PesaGuard identity key-ring configuration is invalid")
        if not isinstance(ring, dict) or not ring or any(
            not isinstance(kid, str) or not isinstance(value, str) or len(value.encode()) < 32
            for kid, value in ring.items()
        ):
            raise HTTPException(503, "PesaGuard identity key-ring configuration is invalid")
        if active_kid not in ring:
            raise HTTPException(503, "PesaGuard identity active signing key ID is missing from the configured key ring")
        return ring, active_kid
    # Backward-compatible single-key mode for deployments that have not migrated to
    # the PesaGuard JWT_KEYS_JSON/JWT_ACTIVE_KID rotation configuration yet.
    secret = settings.api_key_auth_jwt_secret
    if not secret or len(secret.encode()) < 32:
        raise HTTPException(503, "API key management authentication is not configured with a valid signing key")
    return {"current": secret}, "current"


def require_user_claims(authorization: str | None = Header(default=None, alias="Authorization")):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "A valid developer or PesaGuard user access token is required")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "A valid developer or PesaGuard user access token is required")

    # Developer-platform access tokens use their own signing secret, issuer and audience.
    # They never share the internal operator session secret or service API key.
    try:
        untrusted = jwt.decode(token, options={"verify_signature": False, "verify_exp": False, "verify_aud": False})
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid access token")
    if untrusted.get("iss") == settings.developer_access_token_issuer:
        secret = settings.developer_access_token_secret
        if not secret or len(secret.encode()) < 32:
            raise HTTPException(503, "Developer API-key management authentication is not configured")
        try:
            claims = jwt.decode(
                token, secret, algorithms=["HS256"], issuer=settings.developer_access_token_issuer,
                audience=settings.developer_access_token_audience,
                options={"require": ["exp", "iat", "nbf", "jti", "sub", "tenant_id", "type", "iss", "aud", "auth_version", "scope"]},
                leeway=15,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Access token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(401, "Invalid developer access token")
        if claims.get("type") != "access" or not isinstance(claims.get("sub"), str) or not isinstance(claims.get("tenant_id"), str) or not isinstance(claims.get("session_id"), str):
            raise HTTPException(401, "A valid developer access token is required")
        # Re-check account, workspace, and session state on every API-key operation.
        # Revoking a dashboard session therefore also invalidates its short-lived bearer token immediately.
        with SessionLocal() as db:
            account = db.get(DeveloperAccount, claims["sub"])
            workspace = db.get(DeveloperWorkspace, claims["tenant_id"])
            session = db.get(DeveloperSession, claims["session_id"])
            if (not account or account.disabled_at is not None or not account.email_verified_at
                    or not workspace or workspace.owner_user_id != account.id
                    or not session or session.user_id != account.id or session.revoked_at is not None):
                raise HTTPException(401, "Developer account, workspace, or session is unavailable")
            session_expiry = session.expires_at
            if session_expiry.tzinfo is None:
                session_expiry = session_expiry.replace(tzinfo=timezone.utc)
            if session_expiry <= datetime.now(timezone.utc):
                raise HTTPException(401, "Developer session has expired")
            claims["org_id"] = workspace.id
            claims["organization_id"] = workspace.id
            claims["organization_verified"] = workspace.verified is True
            claims["production_access_approved"] = workspace.production_access_approved is True
            claims["roles"] = ["owner"]
        return claims

    expected_issuer = settings.api_key_auth_jwt_issuer
    expected_audience = settings.api_key_auth_jwt_audience
    if settings.app_env.lower() in {"production", "staging"} and (not expected_issuer or not expected_audience):
        raise HTTPException(503, "API key management requires the PesaGuard JWT issuer and audience")

    try:
        ring, default_kid = _trusted_identity_signing_keys()
        header = jwt.get_unverified_header(token)
        kid = header.get("kid") or default_kid
        if not isinstance(kid, str) or kid not in ring or header.get("alg") != "HS256":
            raise jwt.InvalidTokenError("Untrusted signing key")
        options = {
            "require": ["exp", "iat", "nbf", "jti", "sub", "tenant_id", "session_id", "type", "iss", "aud", "auth_version", "scope"],
            "verify_aud": bool(expected_audience),
            "verify_iss": bool(expected_issuer),
        }
        claims = jwt.decode(
            token, ring[kid], algorithms=["HS256"], options=options,
            audience=expected_audience or None, issuer=expected_issuer or None,
            leeway=30,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Access token has expired")
    except jwt.ImmatureSignatureError:
        raise HTTPException(401, "Access token is not valid yet")
    except jwt.InvalidIssuerError:
        raise HTTPException(401, "Invalid access token issuer")
    except jwt.InvalidAudienceError:
        raise HTTPException(401, "Invalid access token audience")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid PesaGuard access token")
    except HTTPException:
        raise

    if claims.get("type") != "access":
        raise HTTPException(401, "A PesaGuard access token is required; refresh tokens are not accepted")
    subject = claims.get("sub")
    org_id = claims.get("organization_id") or claims.get("org_id") or claims.get("tenant_id")
    if not isinstance(subject, str) or not subject.strip() or not isinstance(org_id, str) or not org_id.strip():
        raise HTTPException(403, "Access token must identify a user and a tenant or organization")
    normalized = dict(claims)
    normalized["org_id"] = org_id
    normalized["sub"] = subject
    return normalized

def _roles(claims: dict) -> set[str]:
    """Normalize trusted role claims defensively; malformed role values grant no privilege."""
    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, (list, tuple, set)):
        return set()
    return {role.strip().lower() for role in roles if isinstance(role, str) and role.strip()}

def _require_org_admin(claims: dict):
    if not ({"owner", "admin"} & _roles(claims)):
        raise HTTPException(403, "Only an organization owner or admin can manage API keys")

def _audit(db: Session, *, org_id: str, actor: str, action: str, key_id: str | None = None, details: dict | None = None):
    db.add(ApiKeyAuditEvent(
        organization_id=org_id[:200], actor_user_id=str(actor)[:200], api_key_id=key_id,
        action=action[:80], details=details or {}, created_at=datetime.now(timezone.utc)
    ))

class CreateApiKey(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    environment: str
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    scopes: list[str] = Field(default_factory=lambda: ["registry:read"])

# Customer-issued keys are read-only lookup credentials. Ingestion scopes are internal-only
# because ingestion writes into the shared canonical registry and job data is not tenant-scoped.
ALLOWED_SCOPES = {"registry:read", "sources:read"}


def _create_key(db: Session, claims: dict, payload: CreateApiKey, commit: bool = True):
    # Key creation is a privileged organization operation in both environments.
    # UI hiding is not authorization; enforce the policy at the shared backend boundary.
    _require_org_admin(claims)
    env = payload.environment.lower().strip()
    if env not in {"sandbox", "production"}:
        raise HTTPException(422, "environment must be sandbox or production")
    active_count = db.scalar(select(func.count()).select_from(ApiKey).where(
        ApiKey.organization_id == str(claims["org_id"]), ApiKey.status == "active"
    )) or 0
    if active_count >= 25:
        raise HTTPException(409, "This organization has reached the limit of 25 active API keys. Revoke an unused key first.")
    roles = _roles(claims)
    if env == "production" and not payload.expires_in_days:
        raise HTTPException(422, "Production API keys must have an expiry date (maximum 365 days)")
    if env == "production" and not (claims.get("organization_verified") is True and claims.get("production_access_approved") is True and ({"owner", "admin"} & set(roles))):
        raise HTTPException(403, "Production keys require a verified organization, approved production access, and an owner/admin role. Submit a production-access request first.")
    if not payload.scopes or not set(payload.scopes).issubset(ALLOWED_SCOPES):
        raise HTTPException(422, "One or more requested scopes are not allowed")
    prefix = "pg_sandbox_" if env == "sandbox" else "pg_live_"
    secret = prefix + secrets.token_urlsafe(36)
    now = datetime.now(timezone.utc)
    expires = None
    if payload.expires_in_days:
        expires = now + timedelta(days=payload.expires_in_days)
    row = ApiKey(
        id=str(uuid.uuid4()), organization_id=str(claims["org_id"])[:200],
        created_by_user_id=str(claims["sub"])[:200], name=payload.name.strip(),
        environment=env, key_prefix=secret[:22], secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        scopes=payload.scopes, status="active", created_at=now, expires_at=expires,
    )
    db.add(row)
    _audit(db, org_id=row.organization_id, actor=row.created_by_user_id, action="api_key.created", key_id=row.id, details={"environment": env, "name": row.name, "scopes": payload.scopes})
    if commit:
        db.commit()
    return {"id": row.id, "name": row.name, "environment": row.environment, "key_prefix": row.key_prefix,
            "secret": secret, "scopes": row.scopes, "status": row.status, "created_at": now.isoformat(),
            "expires_at": expires.isoformat() if expires else None,
            "warning": "Copy this secret now. It will not be shown again."}

def _serialize(row: ApiKey):
    return {"id": row.id, "name": row.name, "environment": row.environment, "key_prefix": row.key_prefix,
            "scopes": row.scopes or [], "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else None,
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None}

def _queue_key_email(background_tasks: BackgroundTasks, claims: dict, *, template_id: str, subject: str, body: str, event_id: str):
    email = claims.get("email")
    if not isinstance(email, str) or "@" not in email:
        return
    background_tasks.add_task(_send_key_email_best_effort, email, subject, body, template_id, event_id)


def _send_key_email_best_effort(email: str, subject: str, body: str, template_id: str, event_id: str):
    try:
        send_transactional_email(email, subject, body, template_id=template_id, idempotency_key=event_id)
    except Exception as exc:
        logging.getLogger(__name__).warning("api_key_notice_failed template=%s error_type=%s",
                                            template_id, type(exc).__name__)


def _queue_workspace_webhook_event(background_tasks: BackgroundTasks, workspace_id: str, event_type: str, payload: dict):
    """Queue signed event deliveries only for endpoints owned by this workspace."""
    # Local import avoids a module-import cycle with the developer platform router.
    from .developer_platform import _deliver_webhook
    with SessionLocal() as db:
        hooks = db.scalars(select(DeveloperWebhook).where(
            DeveloperWebhook.workspace_id == workspace_id,
            DeveloperWebhook.enabled.is_(True),
        )).all()
        hook_ids = [hook.id for hook in hooks if event_type in (hook.events or [])]
    for hook_id in hook_ids:
        background_tasks.add_task(_deliver_webhook, hook_id, workspace_id, event_type, payload)


@router.get("/me")
def current_identity(claims: dict = Depends(require_user_claims)):
    roles = sorted(_roles(claims))
    return {
        "user_id": str(claims["sub"]),
        "organization_id": str(claims["org_id"]),
        "tenant_id": str(claims.get("tenant_id") or claims["org_id"]),
        "roles": roles,
        "organization_verified": claims.get("organization_verified") is True,
        "production_key_eligible": claims.get("organization_verified") is True and claims.get("production_access_approved") is True and bool({"owner", "admin"} & set(roles)),
        "production_access_approved": claims.get("production_access_approved") is True,
        "identity_issuer": claims.get("iss"),
        "token_expires_at": int(claims["exp"]),
    }


@router.get("")
def list_api_keys(claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    rows = db.scalars(select(ApiKey).where(ApiKey.organization_id == str(claims["org_id"])).order_by(ApiKey.created_at.desc())).all()
    return {"items": [_serialize(row) for row in rows]}

@router.post("", status_code=201)
def create_api_key(payload: CreateApiKey, background_tasks: BackgroundTasks, claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    result = _create_key(db, claims, payload)
    _queue_workspace_webhook_event(background_tasks, str(claims["org_id"]), "api_key.created",
        {"id": result["id"], "name": result["name"], "environment": result["environment"],
         "key_prefix": result["key_prefix"], "scopes": result["scopes"], "expires_at": result["expires_at"]})
    _queue_key_email(background_tasks, claims, template_id="api_key.created",
        subject=f"PesaGuard {result['environment']} API key created",
        body=f"An API key named {result['name']} was created for the {result['environment']} environment.\n\nKey prefix: {result['key_prefix']}\nScopes: {', '.join(result['scopes'])}\n\nFor security, PesaGuard will never email the full secret. If you did not create this key, revoke it immediately and review your audit events.",
        event_id=f"api-key-created:{result['id']}")
    return result

@router.post("/{key_id}/rotate", status_code=201)
def rotate_api_key(key_id: str, background_tasks: BackgroundTasks, claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    _require_org_admin(claims)
    row = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == str(claims["org_id"])))
    if not row:
        raise HTTPException(404, "API key not found")
    if row.status != "active":
        raise HTTPException(409, "Only active API keys can be rotated")
    old_id, env, name = row.id, row.environment, row.name
    scopes = [scope for scope in (row.scopes or []) if scope in ALLOWED_SCOPES] or ["registry:read"]
    expires_in_days = 90 if (env == "production" or row.expires_at) else None
    # Revoke and re-issue in ONE transaction: if the new key is refused (verification, limits)
    # nothing is committed and the existing key keeps working.
    row.status = "revoked"; row.revoked_at = datetime.now(timezone.utc)
    db.flush()
    _audit(db, org_id=row.organization_id, actor=str(claims["sub"]), action="api_key.rotated_revoked", key_id=old_id, details={"environment": env})
    try:
        result = _create_key(db, claims, CreateApiKey(name=name, environment=env, scopes=scopes, expires_in_days=expires_in_days), commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    _queue_workspace_webhook_event(background_tasks, str(claims["org_id"]), "api_key.rotated",
        {"id": result["id"], "name": result["name"], "environment": result["environment"],
         "key_prefix": result["key_prefix"], "scopes": result["scopes"], "expires_at": result["expires_at"]})
    _queue_key_email(background_tasks, claims, template_id="api_key.rotated",
        subject=f"PesaGuard {env} API key rotated",
        body=f"The API key named {name} was rotated in the {env} environment.\n\nNew key prefix: {result['key_prefix']}\nThe old key has been revoked. Update your integration using the new secret shown once in the dashboard; it is not included in this email. If you did not request this rotation, review your workspace audit events.",
        event_id=f"api-key-rotated:{old_id}:{result['id']}")
    return result


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(key_id: str, background_tasks: BackgroundTasks, claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    _require_org_admin(claims)
    row = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == str(claims["org_id"])))
    if not row:
        raise HTTPException(404, "API key not found")
    if row.status == "active":
        row.status = "revoked"; row.revoked_at = datetime.now(timezone.utc)
        _audit(db, org_id=row.organization_id, actor=str(claims["sub"]), action="api_key.revoked", key_id=row.id, details={"environment": row.environment})
        db.commit()
        _queue_workspace_webhook_event(background_tasks, str(claims["org_id"]), "api_key.revoked",
            {"id": row.id, "name": row.name, "environment": row.environment, "key_prefix": row.key_prefix})
        _queue_key_email(background_tasks, claims, template_id="api_key.revoked",
            subject=f"PesaGuard {row.environment} API key revoked",
            body=f"The API key named {row.name} ({row.key_prefix}) was revoked in the {row.environment} environment. Requests using this key should now fail authentication. If you did not revoke it, review your audit events and rotate any other potentially exposed credentials.",
            event_id=f"api-key-revoked:{row.id}")
    return None

@router.get("/audit/events")
def list_key_audit(claims: dict = Depends(require_user_claims), db: Session = Depends(get_db), limit: int = 100):
    limit = max(1, min(limit, 200))
    rows = db.scalars(select(ApiKeyAuditEvent).where(ApiKeyAuditEvent.organization_id == str(claims["org_id"])).order_by(ApiKeyAuditEvent.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": r.id, "api_key_id": r.api_key_id, "action": r.action, "details": r.details or {}, "created_at": r.created_at.isoformat()} for r in rows]}
