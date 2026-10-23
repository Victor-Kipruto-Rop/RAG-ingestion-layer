import asyncio
import hashlib
import hmac
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from fastapi import Header, HTTPException, Request
from redis import Redis
from sqlalchemy import select
from .config import settings
from .database import SessionLocal
from .models import ManagedAPIKey, APIKeySecurityEvent

@lru_cache(maxsize=1)
def _redis_client():
    if not settings.redis_url: return None
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)

_nonce_lock=threading.Lock();_seen_nonces={}
_bucket_lock=threading.Lock();_local_buckets={}
_TOKEN_BUCKET_LUA = """
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens')) or capacity
local last = tonumber(redis.call('HGET', KEYS[1], 'last')) or now
tokens = math.min(capacity, tokens + math.max(0, now - last) * refill)
if tokens < 1 then
  redis.call('HSET', KEYS[1], 'tokens', tokens, 'last', now)
  redis.call('EXPIRE', KEYS[1], ttl)
  return 0
end
tokens = tokens - 1
redis.call('HSET', KEYS[1], 'tokens', tokens, 'last', now)
redis.call('EXPIRE', KEYS[1], ttl)
return 1
"""

def _check_nonce_local(nonce, expires_at):
    now=time.time()
    with _nonce_lock:
        for key,expiry in list(_seen_nonces.items()):
            if expiry<=now: _seen_nonces.pop(key,None)
        if nonce in _seen_nonces: return False
        _seen_nonces[nonce]=expires_at
        return True

async def _check_nonce(nonce,ttl):
    client=_redis_client();nonce_key='registry:hmac:nonce:'+hashlib.sha256(nonce.encode()).hexdigest()
    if client is not None:
        try: return bool(await asyncio.to_thread(client.set,nonce_key,'1',nx=True,ex=ttl))
        except Exception:
            if settings.require_hmac: raise HTTPException(503,'Replay protection is temporarily unavailable')
    return _check_nonce_local(nonce_key,time.time()+ttl)

async def _take_token(identity,request):
    capacity=max(1,settings.registry_rate_limit_capacity);refill=max(.01,settings.registry_rate_limit_refill_per_second)
    client=_redis_client();client_key=hashlib.sha256(identity.encode()).hexdigest();key='registry:rate:'+client_key
    ttl=max(60,int((capacity/refill)*2))
    if client is not None:
        try:
            allowed=await asyncio.to_thread(client.eval,_TOKEN_BUCKET_LUA,1,key,capacity,refill,time.time(),ttl)
            if not allowed: raise HTTPException(429,'Registry lookup rate limit exceeded',headers={'Retry-After':'1'})
            return
        except HTTPException: raise
        except Exception:
            if settings.app_env.lower()=='production' and settings.redis_url: raise HTTPException(503,'Distributed rate limiter is unavailable')
    now=time.monotonic()
    with _bucket_lock:
        tokens,last=_local_buckets.get(key,(float(capacity),now));tokens=min(float(capacity),tokens+max(0.0,now-last)*refill)
        if tokens<1:
            _local_buckets[key]=(tokens,now);raise HTTPException(429,'Registry lookup rate limit exceeded',headers={'Retry-After':'1'})
        _local_buckets[key]=(tokens-1,now)

def _effective_environment():
    configured=settings.datasource_environment.strip().lower()
    if configured in {'sandbox','production'}: return configured
    return 'production' if settings.app_env.lower()=='production' else 'sandbox'

def _record_security_event(request,event_type,key=None,key_environment=None,details=None):
    key_id=key.get('id') if isinstance(key,dict) else getattr(key,'id',None)
    key_prefix=key.get('key_prefix') if isinstance(key,dict) else getattr(key,'key_prefix',None)
    try:
        with SessionLocal() as db:
            db.add(APIKeySecurityEvent(key_id=key_id,key_prefix=key_prefix,event_type=event_type,
                expected_environment=_effective_environment(),key_environment=key_environment,
                endpoint=request.url.path[:300],http_method=request.method[:12],
                request_id=getattr(request.state,'request_id',None),
                client_ip=request.client.host if request.client else None,details=details or {}))
            db.commit()
    except Exception:
        # No raw credential is stored or logged. Authentication remains denied.
        return

def _managed_key_from_db(raw_key):
    parts=raw_key.split('_',3)
    if len(parts)!=4 or parts[0]!='pg' or parts[1] not in {'sandbox','live'}: return None
    prefix='_'.join(parts[:3]);digest=hashlib.sha256(raw_key.encode()).hexdigest()
    try:
        with SessionLocal() as db:
            key=db.scalar(select(ManagedAPIKey).where(ManagedAPIKey.key_prefix==prefix))
            if not key or not hmac.compare_digest(key.secret_hash,digest): return None
            # The visible prefix and stored environment must agree; never trust a prefix alone.
            prefix_environment = 'production' if parts[1] == 'live' else 'sandbox'
            if key.environment != prefix_environment: return None
            now=datetime.now(timezone.utc);expires=key.expires_at
            if expires is not None and expires.tzinfo is None: expires=expires.replace(tzinfo=timezone.utc)
            if key.status!='active' or (expires is not None and expires<=now): return None
            result={'id':key.id,'key_prefix':key.key_prefix,'environment':key.environment,'scopes':list(key.scopes or [])}
            key.last_used_at=now;db.commit();return result
    except Exception as exc:
        raise HTTPException(503,'Managed API-key store is unavailable; apply the reviewed key-management migration.') from exc

def _required_scope(request):
    path=request.url.path;method=request.method.upper()
    if path.startswith('/api/v1/ingestion/uploads'): return 'ingestion:write' if method in {'POST','PUT','PATCH'} else 'registry:read'
    if path.startswith('/api/v1/sources') and method in {'POST','PATCH','DELETE'}: return 'sources:write'
    if path.startswith('/api/v1/exports/'): return 'exports:read'
    if path.startswith('/api/v1/quality/') or path.startswith('/api/v1/registry/match-candidates') or path.startswith('/api/v1/warehouse/'): return 'registry:read'
    if path.startswith('/api/v1/registry/') or path.startswith('/api/v1/organizations') or path.startswith('/api/v1/metrics/') or path.startswith('/api/v1/ingestion/jobs') or path.startswith('/api/v1/sources'): return 'registry:read'
    return None

async def require_api_key(request:Request,x_api_key:str|None=Header(default=None,alias='X-API-Key'),
    x_internal_signature:str|None=Header(default=None,alias='X-Internal-Signature'),
    x_internal_timestamp:str|None=Header(default=None,alias='X-Internal-Timestamp'),
    x_internal_nonce:str|None=Header(default=None,alias='X-Internal-Nonce')):
    if x_internal_signature is not None:
        secret=settings.hmac_shared_secret
        if not secret or not x_internal_timestamp or not x_internal_nonce: raise HTTPException(401,'Invalid internal signature headers')
        try: timestamp=int(x_internal_timestamp)
        except (TypeError,ValueError): raise HTTPException(401,'Invalid internal signature timestamp')
        if abs(time.time()-timestamp)>max(30,settings.hmac_clock_skew_seconds): raise HTTPException(401,'Internal signature timestamp expired')
        if not x_internal_nonce or len(x_internal_nonce)>200: raise HTTPException(401,'Invalid internal signature nonce')
        body=await request.body();body_hash=hashlib.sha256(body).hexdigest()
        canonical='\n'.join([str(timestamp),x_internal_nonce,request.method.upper(),request.url.path,request.url.query,body_hash])
        expected=hmac.new(secret.encode(),canonical.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,x_internal_signature.lower()): raise HTTPException(401,'Invalid internal signature')
        if not await _check_nonce(x_internal_nonce,max(60,settings.hmac_nonce_ttl_seconds)): raise HTTPException(401,'Internal request replay detected')
        identity='hmac-client:'+(request.client.host if request.client else 'unknown')
        request.state.api_key_scopes=['registry:read','ingestion:write','sources:write','exports:read']
    else:
        if not x_api_key: raise HTTPException(401,'Invalid or missing API key')
        managed_prefix=x_api_key.startswith('pg_sandbox_') or x_api_key.startswith('pg_live_')
        if managed_prefix and settings.managed_api_keys_enabled:
            managed=_managed_key_from_db(x_api_key)
            if not managed:
                _record_security_event(request,'invalid_managed_key')
                raise HTTPException(401,'Invalid, expired, or revoked API key')
            expected_env=_effective_environment();key_env=managed['environment']
            if key_env!=expected_env:
                _record_security_event(request,'environment_mismatch',managed,key_env,{'reason':'key_used_in_wrong_environment'})
                raise HTTPException(403,detail={'code':'API_KEY_ENVIRONMENT_MISMATCH','message':f'This is a {key_env} API key and can only be used with the {key_env} datasource environment.','key_environment':key_env,'request_environment':expected_env})
            scope=_required_scope(request)
            if scope and scope not in managed['scopes']:
                _record_security_event(request,'scope_denied',managed,key_env,{'required_scope':scope})
                raise HTTPException(403,detail={'code':'API_KEY_SCOPE_DENIED','message':'This API key does not have permission for this operation.','required_scope':scope})
            identity='managed-api-key:'+managed['id'];request.state.api_key_scopes=managed['scopes'];request.state.api_key_id=managed['id']
        else:
            if settings.require_hmac: raise HTTPException(401,'Signed internal request required')
            keys=settings.api_key_list
            if not keys or not any(hmac.compare_digest(x_api_key,key) for key in keys): raise HTTPException(401,'Invalid or missing API key')
            identity='api-key:'+hashlib.sha256(x_api_key.encode()).hexdigest()
            request.state.api_key_scopes=['registry:read','ingestion:write','sources:write','exports:read']
    if request.url.path in {'/api/v1/registry/lookup','/api/v1/registry/search'}: await _take_token(identity,request)
    return identity
