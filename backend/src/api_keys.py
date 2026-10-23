from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .managed_keys import (
    APIKeySecurityEvent,
    ManagedAPIKey,
    issue_key,
    key_public,
    record_security_event,
    require_key_management_token,
)

router = APIRouter(prefix="/api/v1/admin/api-keys", tags=["API key management"])
Environment = Literal["sandbox", "production"]
ALLOWED_SCOPES = {"registry:read", "ingestion:write"}


class CreateAPIKeyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    environment: Environment
    scopes: list[str] = Field(default_factory=lambda: ["registry:read"], min_length=1, max_length=2)
    expires_in_days: int | None = Field(default=90, ge=1, le=365)


def _authorize(token: str | None):
    require_key_management_token(token)


def _new_key(db: Session, name: str, environment: str, scopes: list[str], expires_in_days: int | None, rotated_from_id: str | None = None):
    issued = issue_key(name, environment, scopes, expires_in_days, rotated_from_id=rotated_from_id)
    key = ManagedAPIKey(**{k: v for k, v in issued.items() if k != "secret"})
    db.add(key)
    return key, issued["secret"]


@router.get("")
def list_keys(
    x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token"),
    environment: Environment | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _authorize(x_key_management_token)
    stmt = select(ManagedAPIKey)
    if environment:
        stmt = stmt.where(ManagedAPIKey.environment == environment)
    keys = db.scalars(stmt.order_by(ManagedAPIKey.created_at.desc()).limit(500)).all()
    return {"items": [key_public(key) for key in keys], "count": len(keys)}


@router.post("", status_code=201)
def create_key(
    payload: CreateAPIKeyRequest,
    request: Request,
    x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token"),
    db: Session = Depends(get_db),
):
    _authorize(x_key_management_token)
    scopes = sorted(set(payload.scopes))
    if not scopes or not set(scopes).issubset(ALLOWED_SCOPES):
        raise HTTPException(422, {"code": "INVALID_SCOPES", "message": "Allowed scopes: registry:read, ingestion:write"})
    key, secret = _new_key(db, payload.name.strip(), payload.environment, scopes, payload.expires_in_days)
    db.flush()
    record_security_event(db, key, "key_created", payload.environment, request, "Created through protected operator endpoint")
    db.commit()
    db.refresh(key)
    return {
        "key": key_public(key),
        "secret": secret,
        "warning": "Copy this secret now. It will not be shown again.",
    }


@router.post("/{key_id}/rotate", status_code=201)
def rotate_key(
    key_id: str,
    request: Request,
    x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token"),
    db: Session = Depends(get_db),
):
    _authorize(x_key_management_token)
    old = db.get(ManagedAPIKey, key_id)
    if not old:
        raise HTTPException(404, "API key not found")
    if old.status != "active":
        raise HTTPException(409, "Only an active API key can be rotated")
    now = datetime.now(timezone.utc)
    old.status = "revoked"
    old.revoked_at = now
    replacement, secret = _new_key(db, old.name, old.environment, list(old.scopes or ["registry:read"]), 90, rotated_from_id=old.id)
    db.flush()
    record_security_event(db, old, "key_rotated", old.environment, request, f"replacement_key_id={replacement.id}")
    record_security_event(db, replacement, "key_created_by_rotation", replacement.environment, request, f"rotated_from_id={old.id}")
    db.commit()
    db.refresh(replacement)
    return {"key": key_public(replacement), "secret": secret, "warning": "The previous key is revoked. Copy this replacement secret now; it will not be shown again."}


@router.post("/{key_id}/revoke")
def revoke_key(
    key_id: str,
    request: Request,
    x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token"),
    db: Session = Depends(get_db),
):
    _authorize(x_key_management_token)
    key = db.get(ManagedAPIKey, key_id)
    if not key:
        raise HTTPException(404, "API key not found")
    if key.status != "revoked":
        key.status = "revoked"
        key.revoked_at = datetime.now(timezone.utc)
        record_security_event(db, key, "key_revoked", key.environment, request)
        db.commit()
    return {"key": key_public(key), "message": "API key revoked."}


@router.get("/security-events")
def security_events(
    x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _authorize(x_key_management_token)
    rows = db.scalars(select(APIKeySecurityEvent).order_by(APIKeySecurityEvent.created_at.desc()).limit(limit)).all()
    return {
        "items": [{
            "id": row.id,
            "key_id": row.key_id,
            "key_prefix": row.key_prefix,
            "event_type": row.event_type,
            "requested_environment": row.requested_environment,
            "endpoint": row.endpoint,
            "request_id": row.request_id,
            "details": row.details,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        } for row in rows],
        "count": len(rows),
    }
