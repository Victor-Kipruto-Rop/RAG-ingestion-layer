"""User API-key management. Requires a trusted PesaGuard-issued HS256 access token.
The dashboard must never receive the datasource's internal REGISTRY_API_KEYS secret.
"""
import base64, hashlib, hmac, json, secrets, time, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import ApiKey, ApiKeyAuditEvent

router = APIRouter(prefix="/api/v1/keys", tags=["API key management"])

def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def require_user_claims(authorization: str | None = Header(default=None, alias="Authorization")):
    secret = settings.api_key_auth_jwt_secret
    if not secret:
        raise HTTPException(503, "API key management authentication is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "A valid PesaGuard user access token is required")
    token = authorization[7:].strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(401, "Invalid access token")
    try:
        header = json.loads(_b64url_decode(parts[0]))
        claims = json.loads(_b64url_decode(parts[1]))
        signature = _b64url_decode(parts[2])
    except Exception:
        raise HTTPException(401, "Invalid access token")
    if header.get("alg") != "HS256" or header.get("typ", "JWT") != "JWT":
        raise HTTPException(401, "Unsupported access token")
    expected = hmac.new(secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Invalid access token signature")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= time.time():
        raise HTTPException(401, "Access token has expired")
    if not claims.get("sub") or not claims.get("org_id"):
        raise HTTPException(403, "Access token must identify a user and organization")
    expected_issuer = settings.api_key_auth_jwt_issuer
    expected_audience = settings.api_key_auth_jwt_audience
    if settings.app_env.lower() == 'production' and (not expected_issuer or not expected_audience):
        raise HTTPException(503, 'API key management requires configured JWT issuer and audience')
    if expected_issuer and claims.get("iss") != expected_issuer:
        raise HTTPException(401, "Invalid access token issuer")
    audience = claims.get("aud")
    if expected_audience and not (audience == expected_audience or isinstance(audience, list) and expected_audience in audience):
        raise HTTPException(401, "Invalid access token audience")
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

def _create_key(db: Session, claims: dict, payload: CreateApiKey):
    env = payload.environment.lower().strip()
    if env not in {"sandbox", "production"}:
        raise HTTPException(422, "environment must be sandbox or production")
    roles = _roles(claims)
    if env == "production" and not payload.expires_in_days:
        raise HTTPException(422, "Production API keys must have an expiry date (maximum 365 days)")
    if env == "production" and not (claims.get("organization_verified") is True and ({"owner", "admin"} & set(roles))):
        raise HTTPException(403, "Production keys require a verified organization and an owner/admin role")
    allowed_scopes = {"registry:read", "ingestion:read", "ingestion:write", "sources:read"}
    if not payload.scopes or not set(payload.scopes).issubset(allowed_scopes):
        raise HTTPException(422, "One or more requested scopes are not allowed")
    prefix = "pg_sandbox_" if env == "sandbox" else "pg_live_"
    secret = prefix + secrets.token_urlsafe(36)
    now = datetime.now(timezone.utc)
    expires = None
    if payload.expires_in_days:
        from datetime import timedelta
        expires = now + timedelta(days=payload.expires_in_days)
    row = ApiKey(
        id=str(uuid.uuid4()), organization_id=str(claims["org_id"])[:200],
        created_by_user_id=str(claims["sub"])[:200], name=payload.name.strip(),
        environment=env, key_prefix=secret[:22], secret_hash=hashlib.sha256(secret.encode()).hexdigest(),
        scopes=payload.scopes, status="active", created_at=now, expires_at=expires,
    )
    db.add(row)
    _audit(db, org_id=row.organization_id, actor=row.created_by_user_id, action="api_key.created", key_id=row.id, details={"environment": env, "name": row.name, "scopes": payload.scopes})
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
    old_id, env, name, scopes = row.id, row.environment, row.name, row.scopes or ["registry:read"]
    row.status = "revoked"; row.revoked_at = datetime.now(timezone.utc)
    _audit(db, org_id=row.organization_id, actor=str(claims["sub"]), action="api_key.rotated_revoked", key_id=old_id, details={"environment": env})
    db.commit()
    return _create_key(db, claims, CreateApiKey(name=name, environment=env, scopes=scopes, expires_in_days=90))

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
