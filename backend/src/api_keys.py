import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db

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
    return {"id": row["id"], "name": row["name"], "key_prefix": row["key_prefix"],
            "environment": row["environment"], "scopes": row["scopes"], "status": row["status"],
            "created_by": row["created_by"], "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
            "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
            "revoked_at": row["revoked_at"].isoformat() if row["revoked_at"] else None}

def _issue(db: Session, payload: CreateKey, actor: str, rotated_from_id: str | None = None):
    if payload.environment not in {"sandbox", "production"}:
        raise HTTPException(422, "environment must be sandbox or production")
    if not payload.name.strip():
        raise HTTPException(422, "name is required")
    if not payload.scopes or len(set(payload.scopes)) != len(payload.scopes) or not set(payload.scopes).issubset(ALLOWED_SCOPES):
        raise HTTPException(422, {"code": "INVALID_SCOPES", "allowed_scopes": sorted(ALLOWED_SCOPES)})
    marker = "pg_sandbox_" if payload.environment == "sandbox" else "pg_live_"
    secret = marker + secrets.token_urlsafe(32)
    prefix = marker + secret[len(marker):len(marker)+8]
    digest = hashlib.sha256(secret.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None
    db.execute(text("""INSERT INTO api_keys
      (id,name,key_prefix,secret_hash,environment,scopes,status,expires_at,created_by,rotated_from_id)
      VALUES (:id,:name,:prefix,:digest,:environment,CAST(:scopes AS jsonb),'active',:expires,:actor,:rotated_from)"""),
      {"id":str(uuid.uuid4()),"name":payload.name.strip(),"prefix":prefix,"digest":digest,
       "environment":payload.environment,"scopes":json.dumps(payload.scopes),"expires":expires_at,
       "actor":actor[:200],"rotated_from":rotated_from_id})
    db.flush()
    return {"secret":secret,"key":db.execute(text("SELECT * FROM api_keys WHERE key_prefix=:prefix"),{"prefix":prefix}).mappings().one()}

@router.post("", status_code=201)
def create_key(payload: CreateKey, request: Request, db: Session = Depends(get_db),
               x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    issued = _issue(db, payload, "trusted-operator")
    db.commit()
    return {"key":_row(issued["key"]),"secret":issued["secret"],"warning":"Copy this secret now. It will not be shown again."}

@router.get("")
def list_keys(db: Session = Depends(get_db),
              x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    rows = db.execute(text("SELECT * FROM api_keys ORDER BY created_at DESC LIMIT 500")).mappings().all()
    return {"items":[_row(r) for r in rows],"count":len(rows)}

@router.get("/events")
def list_security_events(page:int=1,page_size:int=50,event_type:str|None=None,db:Session=Depends(get_db),
                         x_key_management_token:str|None=Header(default=None,alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    page=max(1,page);page_size=max(1,min(200,page_size))
    where=" WHERE event_type=:event_type" if event_type else ""
    params={"offset":(page-1)*page_size,"limit":page_size}
    if event_type:params["event_type"]=event_type[:60]
    count_params={"event_type":params["event_type"]} if event_type else {}
    total=db.execute(text("SELECT count(*) FROM api_key_security_events"+where),count_params).scalar() or 0
    rows=db.execute(text("SELECT id,api_key_id,key_prefix,event_type,expected_environment,key_environment,endpoint,request_id,source_ip,details,created_at FROM api_key_security_events"+where+" ORDER BY created_at DESC OFFSET :offset LIMIT :limit"),params).mappings().all()
    return {"items":[{"id":row["id"],"api_key_id":row["api_key_id"],"key_prefix":row["key_prefix"],
        "event_type":row["event_type"],"expected_environment":row["expected_environment"],
        "key_environment":row["key_environment"],"endpoint":row["endpoint"],"request_id":row["request_id"],
        "source_ip":row["source_ip"],"details":row["details"] or {},
        "created_at":row["created_at"].isoformat() if row["created_at"] else None} for row in rows],
        "total":total,"page":page,"page_size":page_size}

@router.get("/{key_id}/usage")
def key_usage(key_id:str,days:int=Query(default=30,ge=1,le=90),db:Session=Depends(get_db),
              x_key_management_token:str|None=Header(default=None,alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    key=db.execute(text("SELECT id,key_prefix,environment,name FROM api_keys WHERE id=:id"),{"id":key_id}).mappings().first()
    if not key:raise HTTPException(404,"API key not found")
    since=datetime.now(timezone.utc)-timedelta(days=days)
    totals=db.execute(text("""SELECT count(*) AS total_requests,
      coalesce(sum(CASE WHEN response_status>=400 THEN 1 ELSE 0 END),0) AS error_requests,
      coalesce(avg(duration_ms),0) AS average_duration_ms,
      max(created_at) AS last_request_at
      FROM api_key_usage_events WHERE api_key_id=:id AND created_at>=:since"""),{"id":key_id,"since":since}).mappings().one()
    rows=db.execute(text("""SELECT endpoint,http_method,response_status,count(*) AS requests,
      coalesce(avg(duration_ms),0) AS average_duration_ms
      FROM api_key_usage_events WHERE api_key_id=:id AND created_at>=:since
      GROUP BY endpoint,http_method,response_status ORDER BY requests DESC LIMIT 100"""),{"id":key_id,"since":since}).mappings().all()
    return {"key":{"id":key["id"],"key_prefix":key["key_prefix"],"environment":key["environment"],"name":key["name"]},
      "window_days":days,"total_requests":int(totals["total_requests"] or 0),
      "error_requests":int(totals["error_requests"] or 0),"average_duration_ms":round(float(totals["average_duration_ms"] or 0),3),
      "last_request_at":totals["last_request_at"].isoformat() if totals["last_request_at"] else None,
      "breakdown":[{"endpoint":row["endpoint"],"method":row["http_method"],"status":row["response_status"],
        "requests":int(row["requests"]),"average_duration_ms":round(float(row["average_duration_ms"] or 0),3)} for row in rows]}

@router.post("/{key_id}/revoke")
def revoke_key(key_id: str, db: Session = Depends(get_db),
               x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    row = db.execute(text("SELECT * FROM api_keys WHERE id=:id FOR UPDATE"),{"id":key_id}).mappings().first()
    if not row:
        raise HTTPException(404,"API key not found")
    if row["status"] != "revoked":
        db.execute(text("UPDATE api_keys SET status='revoked', revoked_at=now() WHERE id=:id"),{"id":key_id})
        db.execute(text("""INSERT INTO api_key_security_events
          (id,api_key_id,key_prefix,event_type,endpoint,details)
          VALUES (:id,:key_id,:prefix,'key_revoked','/api/v1/admin/api-keys',CAST(:details AS jsonb))"""),
          {"id":str(uuid.uuid4()),"key_id":key_id,"prefix":row["key_prefix"],"details":json.dumps({"actor":"trusted-operator"})})
        db.commit()
    return {"id":key_id,"status":"revoked"}

@router.post("/{key_id}/rotate", status_code=201)
def rotate_key(key_id: str, db: Session = Depends(get_db),
               x_key_management_token: str | None = Header(default=None, alias="X-Key-Management-Token")):
    _management_auth(x_key_management_token)
    row = db.execute(text("SELECT * FROM api_keys WHERE id=:id FOR UPDATE"),{"id":key_id}).mappings().first()
    if not row or row["status"] != "active" or (row["expires_at"] and row["expires_at"] <= datetime.now(timezone.utc)):
        raise HTTPException(404,"Active API key not found")
    scopes = row["scopes"] if isinstance(row["scopes"], list) else json.loads(row["scopes"])
    days = max(1, min(3650, (row["expires_at"] - datetime.now(timezone.utc)).days)) if row["expires_at"] else None
    payload = CreateKey(name=row["name"], environment=row["environment"], scopes=scopes, expires_in_days=days)
    issued = _issue(db, payload, "trusted-operator", key_id)
    db.execute(text("UPDATE api_keys SET status='revoked',revoked_at=now() WHERE id=:id"),{"id":key_id})
    db.execute(text("""INSERT INTO api_key_security_events
      (id,api_key_id,key_prefix,event_type,endpoint,details)
      VALUES (:id,:key_id,:prefix,'key_rotated','/api/v1/admin/api-keys',CAST(:details AS jsonb))"""),
      {"id":str(uuid.uuid4()),"key_id":key_id,"prefix":row["key_prefix"],"details":json.dumps({"replacement_prefix":issued["key"]["key_prefix"]})})
    db.commit()
    return {"key":_row(issued["key"]),"secret":issued["secret"],"warning":"Copy this secret now. The predecessor has been revoked."}
