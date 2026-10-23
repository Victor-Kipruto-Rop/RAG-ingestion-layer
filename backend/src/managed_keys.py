import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import DateTime, Index, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from .config import settings
from .database import Base, SessionLocal
from .models import json_type, now_utc


class ManagedAPIKey(Base):
    __tablename__ = "managed_api_keys"
    __table_args__ = (
        Index("ix_managed_api_keys_environment_status", "environment", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list] = mapped_column(json_type, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="service-operator")
    rotated_from_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class APIKeySecurityEvent(Base):
    __tablename__ = "api_key_security_events"
    __table_args__ = (Index("ix_api_key_events_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    key_prefix: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    requested_environment: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(300), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)


def runtime_environment() -> str:
    value = settings.datasource_environment.strip().lower()
    if value == "development":
        return "sandbox"
    if value not in {"sandbox", "production"}:
        raise HTTPException(503, "Datasource environment is not configured correctly")
    return value


def _key_hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def issue_key(name: str, environment: str, scopes: list[str], expires_in_days: int | None, created_by: str = "service-operator", rotated_from_id: str | None = None):
    token_secret = secrets.token_hex(32)
    token = f"pg_{'live' if environment == 'production' else 'sandbox'}_{token_secret}"
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "environment": environment,
        "key_prefix": token[:28],
        "key_hash": _key_hash(token),
        "scopes": scopes,
        "status": "active",
        "created_by": created_by,
        "rotated_from_id": rotated_from_id,
        "created_at": now_utc(),
        "last_used_at": None,
        "expires_at": now_utc() + timedelta(days=expires_in_days) if expires_in_days else None,
        "revoked_at": None,
        "secret": token,
    }


def key_public(key: ManagedAPIKey) -> dict:
    return {
        "id": key.id,
        "name": key.name,
        "environment": key.environment,
        "key_prefix": key.key_prefix,
        "scopes": key.scopes or [],
        "status": key.status,
        "created_by": key.created_by,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
        "rotated_from_id": key.rotated_from_id,
    }


def record_security_event(db, key, event_type: str, environment: str, request: Request, details: str | None = None):
    db.add(APIKeySecurityEvent(
        key_id=key.id if key else None,
        key_prefix=key.key_prefix if key else None,
        event_type=event_type,
        requested_environment=environment,
        endpoint=request.url.path[:300],
        request_id=(getattr(request.state, "request_id", None) or request.headers.get("X-Correlation-ID") or "")[:100] or None,
        details=details[:500] if details else None,
    ))


def authenticate_managed_key(token: str, request: Request) -> tuple[bool, str | None, list[str] | None]:
    if not token.startswith(("pg_sandbox_", "pg_live_")):
        return False, None, None

    prefix = token[:28]
    requested_environment = runtime_environment()
    with SessionLocal() as db:
        key = db.scalar(select(ManagedAPIKey).where(ManagedAPIKey.key_prefix == prefix).limit(1))
        if not key or not hmac.compare_digest(key.key_hash, _key_hash(token)):
            record_security_event(db, None, "managed_key_invalid", requested_environment, request)
            db.commit()
            raise HTTPException(401, "Invalid or unknown managed API key")
        if key.status == "revoked" or key.revoked_at is not None:
            record_security_event(db, key, "revoked_key_attempt", requested_environment, request)
            db.commit()
            raise HTTPException(401, "API key has been revoked")
        now = now_utc()
        expiry = key.expires_at
        if key.status == "expired" or (expiry and (expiry.replace(tzinfo=timezone.utc) if expiry.tzinfo is None else expiry) <= now):
            key.status = "expired"
            record_security_event(db, key, "expired_key_attempt", requested_environment, request)
            db.commit()
            raise HTTPException(401, "API key has expired")
        if key.status != "active":
            raise HTTPException(401, "API key is not active")
        if key.environment != requested_environment:
            record_security_event(
                db, key, "environment_mismatch", requested_environment, request,
                f"key_environment={key.environment};request_environment={requested_environment}",
            )
            db.commit()
            raise HTTPException(
                403,
                {
                    "code": "API_KEY_ENVIRONMENT_MISMATCH",
                    "message": f"This is a {key.environment} API key and can only be used with the {key.environment} Datasource environment.",
                    "key_environment": key.environment,
                    "request_environment": requested_environment,
                },
            )
        required_scope = required_scope_for_request(request)
        if required_scope and required_scope not in (key.scopes or []):
            record_security_event(db, key, "scope_denied", requested_environment, request, f"required_scope={required_scope}")
            db.commit()
            raise HTTPException(403, {"code": "API_KEY_SCOPE_DENIED", "message": "This API key does not have permission for this operation.", "required_scope": required_scope})
        key.last_used_at = now
        db.commit()
        return True, key.id, list(key.scopes or [])


def required_scope_for_request(request: Request) -> str | None:
    path = request.url.path
    method = request.method.upper()
    if path.startswith("/api/v1/ingestion/uploads") or (path.startswith("/api/v1/sources") and method in {"POST", "PATCH", "DELETE"}):
        return "ingestion:write"
    if path.startswith("/api/v1/"):
        return "registry:read"
    return None


def require_key_management_token(token: str | None) -> None:
    expected = settings.key_management_token
    if not expected:
        raise HTTPException(503, "API key management is disabled: configure KEY_MANAGEMENT_TOKEN on the server")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(401, "Invalid key-management credentials")
