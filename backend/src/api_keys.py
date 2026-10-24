"""User API-key management. Requires a trusted PesaGuard-issued HS256 access token.
The dashboard must never receive the datasource's internal REGISTRY_API_KEYS secret.
"""
import hashlib, secrets, uuid
from datetime import timedelta

import jwt
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import ApiKey, ApiKeyAuditEvent

router = APIRouter(prefix="/api/v1/keys", tags=["API key management"])

def require_user_claims(authorization: str | None = Header(default=None, alias="Authorization")):
    secret = settings.api_key_auth_jwt_secret
    if not secret:
        raise HTTPException(503, "API key management authentication is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "A valid PesaGuard user access token is required")
    expected_issuer = settings.api_key_auth_jwt_issuer
    expected_audience = settings.api_key_auth_jwt_audience
    if settings.app_env.lower() == 'production' and (not expected_issuer or not expected_audience):
        raise HTTPException(503, 'API key management requires configured JWT issuer and audience')
    options = {"require": ["exp", "sub"], "verify_aud": bool(expected_audience), "verify_iss": bool(expected_issuer)}
    try:
        claims = jwt.decode(
            authorization[7:].strip(), secret, algorithms=["HS256"], options=options,
            audience=expected_audience or None, issuer=expected_issuer or None,
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
        raise HTTPException(401, "Invalid access token")
    if not claims.get("sub") or not claims.get("org_id"):
        raise HTTPException(403, "Access token must identify a user and organization")
    return claims

def _roles(claims: dict) -> set[str]:
    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    return set(roles)

def _require_org_admin(claims: dict):
    if not ({"owner", "admin"} & _roles(claims)):
        raise HTTPException(403, "Only an organization owner or admin can rotate or revoke API keys")

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
    if env == "production" and not (claims.get("organization_verified") is True and ({"owner", "admin"} & set(roles))):
        raise HTTPException(403, "Production keys require a verified organization and an owner/admin role")
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

@router.get("")
def list_api_keys(claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    rows = db.scalars(select(ApiKey).where(ApiKey.organization_id == str(claims["org_id"])).order_by(ApiKey.created_at.desc())).all()
    return {"items": [_serialize(row) for row in rows]}

@router.post("", status_code=201)
def create_api_key(payload: CreateApiKey, claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    return _create_key(db, claims, payload)

@router.post("/{key_id}/rotate", status_code=201)
def rotate_api_key(key_id: str, claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
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
    return result


@router.delete("/{key_id}", status_code=204)
def revoke_api_key(key_id: str, claims: dict = Depends(require_user_claims), db: Session = Depends(get_db)):
    _require_org_admin(claims)
    row = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == str(claims["org_id"])))
    if not row:
        raise HTTPException(404, "API key not found")
    if row.status == "active":
        row.status = "revoked"; row.revoked_at = datetime.now(timezone.utc)
        _audit(db, org_id=row.organization_id, actor=str(claims["sub"]), action="api_key.revoked", key_id=row.id, details={"environment": row.environment})
        db.commit()
    return None

@router.get("/audit/events")
def list_key_audit(claims: dict = Depends(require_user_claims), db: Session = Depends(get_db), limit: int = 100):
    limit = max(1, min(limit, 200))
    rows = db.scalars(select(ApiKeyAuditEvent).where(ApiKeyAuditEvent.organization_id == str(claims["org_id"])).order_by(ApiKeyAuditEvent.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": r.id, "api_key_id": r.api_key_id, "action": r.action, "details": r.details or {}, "created_at": r.created_at.isoformat()} for r in rows]}
