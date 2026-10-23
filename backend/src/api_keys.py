import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import ApiKey, ApiKeySecurityEvent, ApiKeyUsageEvent

router = APIRouter(prefix="/api/v1/admin/api-keys", tags=["API key management"])
ALLOWED_SCOPES = {"registry:read", "registry:write", "sources:write", "exports:read"}

def _management_auth(token: str | None):
    expected = settings.api_key_management_token
    if not expected or not token or not hmac.compare_digest(expected, token):
        raise HTTPException(404, "Not found")

class CreateKey(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    environment: str
    scopes: list[str] = Field(default_factory=lambda: ["registry:read"])
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)

def _row(row):
    scopes = row.scopes if isinstance(row.scopes, list) else []
    return {"id":row.id,"name":row.name,"key_prefix":row.key_prefix,
            "environment":row.environment,"scopes":scopes,"status":row.status,
            "created_by":row.created_by,"created_at":row.created_at.isoformat() if row.created_at else None,
            "expires_at":row.expires_at.isoformat() if row.expires_at else None,
            "last_used_at":row.last_used_at.isoformat() if row.last_used_at else None,
            "revoked_at":row.revoked_at.isoformat() if row.revoked_at else None}

def _issue(db: Session, payload: CreateKey, actor: str, rotated_from_id: str | None = None):
    if payload.environment not in {"sandbox", "production"}:
        raise HTTPException(422, "environment must be sandbox or production")
    if not payload.name.strip():
        raise HTTPException(422, "name is required")
    if not payload.scopes or len(set(payload.scopes)) != len(payload.scopes) or not set(payload.scopes).issubset(ALLOWED_SCOPES):
        raise HTTPException(422, {"code":"INVALID_SCOPES","allowed_scopes":sorted(ALLOWED_SCOPES)})
    marker = "pg_sandbox_" if payload.environment == "sandbox" else "pg_live_"
    secret = marker + secrets.token_urlsafe(32)
    prefix = marker + secret[len(marker):len(marker)+8]
    digest = hashlib.sha256(secret.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
    key = ApiKey(id=str(uuid.uuid4()),name=payload.name.strip(),key_prefix=prefix,secret_hash=digest,
                 environment=payload.environment,scopes=payload.scopes,status="active",expires_at=expires_at,
                 created_by=actor[:200],rotated_from_id=rotated_from_id)
    db.add(key)
    db.flush()
    return {"secret":secret,"key":key}

@router.post("", status_code=201)
def create_key(payload: CreateKey, db: Session = Depends(get_db),
               x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    issued = _issue(db, payload, "trusted-operator")
    db.commit()
    db.refresh(issued["key"])
    return {"key":_row(issued["key"]),"secret":issued["secret"],"warning":"Copy this secret now. It will not be shown again."}

@router.get("")
def list_keys(db: Session = Depends(get_db),
              x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    rows = db.scalars(select(ApiKey).order_by(ApiKey.created_at.desc()).limit(500)).all()
    return {"items":[_row(row) for row in rows],"count":len(rows)}

@router.get("/events")
def list_security_events(page:int=Query(default=1,ge=1),page_size:int=Query(default=50,ge=1,le=200),event_type:str|None=None,
                         db:Session=Depends(get_db),x_key_management_token:str|None=Header(default=None,alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    stmt=select(ApiKeySecurityEvent)
    if event_type:stmt=stmt.where(ApiKeySecurityEvent.event_type==event_type[:60])
    total=db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows=db.scalars(stmt.order_by(ApiKeySecurityEvent.created_at.desc()).offset((page-1)*page_size).limit(page_size)).all()
    return {"items":[{"id":row.id,"api_key_id":row.api_key_id,"key_prefix":row.key_prefix,"event_type":row.event_type,
        "expected_environment":row.expected_environment,"key_environment":row.key_environment,"endpoint":row.endpoint,
        "request_id":row.request_id,"source_ip":row.source_ip,"details":row.details or {},
        "created_at":row.created_at.isoformat() if row.created_at else None} for row in rows],
        "total":total,"page":page,"page_size":page_size}

@router.get("/{key_id}/usage")
def key_usage(key_id:str,days:int=Query(default=30,ge=1,le=90),db:Session=Depends(get_db),
              x_key_management_token:str|None=Header(default=None,alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    key=db.get(ApiKey,key_id)
    if not key:raise HTTPException(404,"API key not found")
    since=datetime.now(timezone.utc)-timedelta(days=days)
    filters=(ApiKeyUsageEvent.api_key_id==key_id,ApiKeyUsageEvent.created_at>=since)
    total=db.scalar(select(func.count()).select_from(ApiKeyUsageEvent).where(*filters)) or 0
    errors=db.scalar(select(func.count()).select_from(ApiKeyUsageEvent).where(*filters,ApiKeyUsageEvent.response_status>=400)) or 0
    average=db.scalar(select(func.avg(ApiKeyUsageEvent.duration_ms)).where(*filters)) or 0
    last=db.scalar(select(func.max(ApiKeyUsageEvent.created_at)).where(*filters))
    rows=db.execute(select(ApiKeyUsageEvent.endpoint,ApiKeyUsageEvent.http_method,ApiKeyUsageEvent.response_status,
        func.count().label("requests"),func.avg(ApiKeyUsageEvent.duration_ms).label("average_duration_ms"))
        .where(*filters).group_by(ApiKeyUsageEvent.endpoint,ApiKeyUsageEvent.http_method,ApiKeyUsageEvent.response_status)
        .order_by(func.count().desc()).limit(100)).mappings().all()
    return {"key":{"id":key.id,"key_prefix":key.key_prefix,"environment":key.environment,"name":key.name},
      "window_days":days,"total_requests":int(total),"error_requests":int(errors),
      "average_duration_ms":round(float(average or 0),3),"last_request_at":last.isoformat() if last else None,
      "breakdown":[{"endpoint":row["endpoint"],"method":row["http_method"],"status":row["response_status"],
        "requests":int(row["requests"]),"average_duration_ms":round(float(row["average_duration_ms"] or 0),3)} for row in rows]}

@router.post("/{key_id}/revoke")
def revoke_key(key_id: str, db: Session = Depends(get_db),
               x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    row=db.scalar(select(ApiKey).where(ApiKey.id==key_id).with_for_update())
    if not row:raise HTTPException(404,"API key not found")
    if row.status != "revoked":
        row.status="revoked"
        row.revoked_at=datetime.now(timezone.utc)
        db.add(ApiKeySecurityEvent(api_key_id=row.id,key_prefix=row.key_prefix,event_type="key_revoked",
            endpoint="/api/v1/admin/api-keys",details={"actor":"trusted-operator"}))
        db.commit()
    return {"id":key_id,"status":"revoked"}

@router.post("/{key_id}/rotate", status_code=201)
def rotate_key(key_id: str, db: Session = Depends(get_db),
               x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    row=db.scalar(select(ApiKey).where(ApiKey.id==key_id).with_for_update())
    if not row or row.status != "active":
        raise HTTPException(404,"Active API key not found")
    expires_at=row.expires_at
    if expires_at and expires_at.tzinfo is None:expires_at=expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at<=datetime.now(timezone.utc):raise HTTPException(404,"Active API key not found")
    scopes=row.scopes if isinstance(row.scopes,list) else []
    days=max(1,min(3650,(expires_at-datetime.now(timezone.utc)).days)) if expires_at else None
    payload=CreateKey(name=row.name,environment=row.environment,scopes=scopes,expires_in_days=days)
    issued=_issue(db,payload,"trusted-operator",row.id)
    old_prefix=row.key_prefix
    row.status="revoked";row.revoked_at=datetime.now(timezone.utc)
    db.add(ApiKeySecurityEvent(api_key_id=row.id,key_prefix=old_prefix,event_type="key_rotated",
        endpoint="/api/v1/admin/api-keys",details={"replacement_prefix":issued["key"].key_prefix}))
    db.commit()
    db.refresh(issued["key"])
    return {"key":_row(issued["key"]),"secret":issued["secret"],"warning":"Copy this secret now. The predecessor has been revoked."}
