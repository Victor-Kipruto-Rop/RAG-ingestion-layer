import hashlib, hmac, secrets, uuid
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import ManagedAPIKey, APIKeySecurityEvent, AuditLog

router=APIRouter(prefix='/api/v1/admin',tags=['API key administration'])
ALLOWED_SCOPES={'registry:read','ingestion:write','sources:write','exports:read'}

class APIKeyCreate(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 environment:Literal['sandbox','production']
 scopes:list[str]=Field(default_factory=lambda:['registry:read'])
 expires_in_days:int|None=Field(default=90,ge=1,le=365)
class APIKeyRotate(BaseModel):
 expires_in_days:int|None=Field(default=90,ge=1,le=365)

def require_admin_token(authorization:str|None=Header(default=None,alias='Authorization')):
 configured=settings.datasource_admin_token
 if not configured: raise HTTPException(503,'API-key administration is not configured. Set DATASOURCE_ADMIN_TOKEN server-side.')
 supplied=authorization[7:].strip() if authorization and authorization.lower().startswith('bearer ') else ''
 if not supplied or not hmac.compare_digest(supplied,configured): raise HTTPException(401,'Valid operator bearer token required')
 return 'operator'

def key_out(key):
 return {'id':key.id,'name':key.name,'environment':key.environment,'key_prefix':key.key_prefix,'scopes':key.scopes or [],
 'status':key.status,'created_by':key.created_by,'created_at':key.created_at.isoformat() if key.created_at else None,
 'last_used_at':key.last_used_at.isoformat() if key.last_used_at else None,'expires_at':key.expires_at.isoformat() if key.expires_at else None,
 'revoked_at':key.revoked_at.isoformat() if key.revoked_at else None}
def new_key(environment):
 public_id=secrets.token_hex(6); token=secrets.token_urlsafe(32)
 prefix=f"pg_{'live' if environment=='production' else 'sandbox'}_{public_id}"
 secret=f'{prefix}_{token}'
 return prefix,secret,hashlib.sha256(secret.encode()).hexdigest()
def expiry(days): return datetime.now(timezone.utc)+timedelta(days=days) if days else None

@router.get('/api-keys')
def list_api_keys(_:str=Depends(require_admin_token),db:Session=Depends(get_db)):
 rows=db.scalars(select(ManagedAPIKey).order_by(desc(ManagedAPIKey.created_at))).all()
 return {'items':[key_out(row) for row in rows],'count':len(rows),'secret_storage':'sha256_hash_only'}

@router.post('/api-keys',status_code=201)
def create_api_key(payload:APIKeyCreate,request:Request,_:str=Depends(require_admin_token),db:Session=Depends(get_db)):
 name=payload.name.strip()
 if len(name)<2: raise HTTPException(422,'name must contain at least 2 non-whitespace characters')
 scopes=sorted(set(payload.scopes))
 if not scopes or any(scope not in ALLOWED_SCOPES for scope in scopes):
  raise HTTPException(422,{'message':'One or more API key scopes are not supported.','allowed_scopes':sorted(ALLOWED_SCOPES)})
 prefix,secret,digest=new_key(payload.environment)
 row=ManagedAPIKey(id=str(uuid.uuid4()),name=name,environment=payload.environment,key_prefix=prefix,secret_hash=digest,scopes=scopes,status='active',created_by='operator',expires_at=expiry(payload.expires_in_days))
 db.add(row)
 db.add(AuditLog(action='managed_api_key_created',actor='operator',details={'key_id':row.id,'key_prefix':prefix,'environment':payload.environment,'scopes':scopes,'request_id':getattr(request.state,'request_id',None)}))
 db.commit();db.refresh(row)
 return {'item':key_out(row),'secret':secret,'warning':'Copy this secret now. It cannot be retrieved again.'}

@router.post('/api-keys/{key_id}/rotate',status_code=201)
def rotate_api_key(key_id:str,payload:APIKeyRotate,request:Request,_:str=Depends(require_admin_token),db:Session=Depends(get_db)):
 old=db.get(ManagedAPIKey,key_id)
 if not old: raise HTTPException(404,'API key not found')
 if old.status!='active': raise HTTPException(409,'Only active API keys can be rotated')
 prefix,secret,digest=new_key(old.environment)
 new=ManagedAPIKey(id=str(uuid.uuid4()),name=old.name,environment=old.environment,key_prefix=prefix,secret_hash=digest,scopes=list(old.scopes or []),status='active',created_by='operator',expires_at=expiry(payload.expires_in_days),rotated_from_id=old.id)
 old.status='revoked';old.revoked_at=datetime.now(timezone.utc)
 db.add(new);db.add(AuditLog(action='managed_api_key_rotated',actor='operator',details={'old_key_id':old.id,'new_key_id':new.id,'environment':old.environment,'request_id':getattr(request.state,'request_id',None)}))
 db.commit();db.refresh(new)
 return {'item':key_out(new),'secret':secret,'warning':'The previous key has been revoked. Copy the new secret now; it cannot be retrieved again.'}

@router.delete('/api-keys/{key_id}')
def revoke_api_key(key_id:str,request:Request,_:str=Depends(require_admin_token),db:Session=Depends(get_db)):
 row=db.get(ManagedAPIKey,key_id)
 if not row: raise HTTPException(404,'API key not found')
 if row.status=='active':
  row.status='revoked';row.revoked_at=datetime.now(timezone.utc)
  db.add(AuditLog(action='managed_api_key_revoked',actor='operator',details={'key_id':row.id,'key_prefix':row.key_prefix,'request_id':getattr(request.state,'request_id',None)}));db.commit()
 return {'item':key_out(row),'message':'API key revoked. It can no longer authenticate requests.'}

@router.get('/security-events')
def security_events(limit:int=100,_:str=Depends(require_admin_token),db:Session=Depends(get_db)):
 rows=db.scalars(select(APIKeySecurityEvent).order_by(desc(APIKeySecurityEvent.created_at)).limit(max(1,min(limit,500)))).all()
 return {'items':[{'id':r.id,'key_id':r.key_id,'key_prefix':r.key_prefix,'event_type':r.event_type,'expected_environment':r.expected_environment,'key_environment':r.key_environment,'endpoint':r.endpoint,'http_method':r.http_method,'request_id':r.request_id,'client_ip':r.client_ip,'details':r.details or {},'created_at':r.created_at.isoformat() if r.created_at else None} for r in rows]}
