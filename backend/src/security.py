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

@lru_cache(maxsize=1)
def _redis_client():
    if not settings.redis_url:
        return None
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)

_nonce_lock = threading.Lock()
_seen_nonces = {}
_bucket_lock = threading.Lock()
_local_buckets = {}
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

def environment_mismatch_detail(key_environment, requested_environment):
    key_label = "sandbox" if key_environment == "sandbox" else "production"
    requested_label = "sandbox" if requested_environment == "sandbox" else "production"
    return {"code":"API_KEY_ENVIRONMENT_MISMATCH",
            "message":f"This API key is restricted to the {key_label} environment and cannot be used in {requested_label}.",
            "key_environment":key_environment,"requested_environment":requested_environment,
            "action":f"Use a {requested_label} API key or switch to the {key_label} endpoint."}

def _audit_key_security_event(key, request, action, details):
    from .models import ApiKeyAuditEvent
    import uuid
    try:
        with SessionLocal() as db:
            db.add(ApiKeyAuditEvent(id=str(uuid.uuid4()), organization_id=key.organization_id,
                actor_user_id=key.created_by_user_id, api_key_id=key.id, action=action,
                details={**details,"method":request.method,"path":request.url.path,
                         "request_id":getattr(request.state,"request_id",None),
                         "remote_address":request.client.host if request.client else None},
                created_at=datetime.now(timezone.utc)))
            db.commit()
    except Exception:
        raise HTTPException(503, "Security audit service is unavailable; request rejected")

def _audit_unknown_environment_mismatch(raw_key, request, key_environment, requested_environment):
    from .models import ApiKeyAuditEvent
    import uuid
    # Separate sandbox/production deployments may have separate key/data stores. In that
    # case the prefix still proves the declared environment, so record the attempt without
    # persisting the supplied secret or pretending we know the owning organization.
    try:
        with SessionLocal() as db:
            db.add(ApiKeyAuditEvent(
                id=str(uuid.uuid4()), organization_id="unknown", actor_user_id="system",
                api_key_id=None, action="api_key.environment_mismatch_unresolved",
                details={"key_environment":key_environment,"requested_environment":requested_environment,
                         "key_prefix":raw_key[:22],"key_fingerprint":hashlib.sha256(raw_key.encode()).hexdigest(),
                         "error_code":"API_KEY_ENVIRONMENT_MISMATCH","method":request.method,
                         "path":request.url.path,"request_id":getattr(request.state,"request_id",None),
                         "remote_address":request.client.host if request.client else None},
                created_at=datetime.now(timezone.utc)))
            db.commit()
    except Exception:
        raise HTTPException(503, "Security audit service is unavailable; request rejected")

def _customer_rate_limit_identity(organization_id: str) -> str:
    """Use a stable tenant bucket so creating more keys cannot multiply lookup quotas."""
    tenant_digest = hashlib.sha256(("tenant:" + str(organization_id)).encode()).hexdigest()
    return "customer-api-key:" + tenant_digest


def _validate_customer_api_key(raw_key, request):
    from .models import ApiKey
    runtime_environment = settings.api_environment.lower().strip()
    if runtime_environment not in {"sandbox", "production"}:
        raise HTTPException(503, "API environment is not configured correctly")
    prefix_environment = "sandbox" if raw_key.startswith("pg_sandbox_") else "production"
    if prefix_environment != runtime_environment:
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        with SessionLocal() as db:
            key = db.scalar(select(ApiKey).where(ApiKey.secret_hash == digest))
        if key:
            _audit_key_security_event(key, request, "api_key.environment_mismatch", {
                "key_environment":key.environment,"requested_environment":runtime_environment,
                "error_code":"API_KEY_ENVIRONMENT_MISMATCH"})
        else:
            _audit_unknown_environment_mismatch(raw_key, request, prefix_environment, runtime_environment)
        raise HTTPException(status_code=403, detail=environment_mismatch_detail(prefix_environment, runtime_environment))
    digest = hashlib.sha256(raw_key.encode()).hexdigest()
    with SessionLocal() as db:
        key = db.scalar(select(ApiKey).where(ApiKey.secret_hash == digest))
        if not key or key.status != "active":
            raise HTTPException(401, "Invalid or revoked API key")
        now = datetime.now(timezone.utc)
        if key.expires_at:
            expires_at = key.expires_at if key.expires_at.tzinfo else key.expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                raise HTTPException(401, "This API key has expired")
        if key.environment != runtime_environment:
            _audit_key_security_event(key, request, "api_key.environment_mismatch", {
                "key_environment":key.environment,"requested_environment":runtime_environment,
                "error_code":"API_KEY_ENVIRONMENT_MISMATCH"})
            raise HTTPException(status_code=403, detail=environment_mismatch_detail(key.environment, runtime_environment))
        path, method = request.url.path, request.method.upper()
        required_scope = None
        if method == "GET" and path in {"/api/v1/registry/lookup", "/api/v1/registry/search", "/api/v1/organizations"}:
            required_scope = "registry:read"
        elif method == "GET" and (path == "/api/v1/sources" or path.startswith("/api/v1/sources/")):
            required_scope = "sources:read"
        # Everything else (ingestion, export, metrics, warehouse, source writes) is internal-only:
        # customer keys are never granted access to bulk data or to the shared canonical registry.
        if not required_scope:
            raise HTTPException(403, {"code":"API_KEY_ENDPOINT_NOT_AVAILABLE","message":"This endpoint is not available to customer API keys.","required_scope":None})
        if required_scope not in (key.scopes or []):
            raise HTTPException(403, {"code":"API_KEY_SCOPE_INSUFFICIENT","message":"This key does not have permission for the requested endpoint.","required_scope":required_scope})
        last_used = key.last_used_at
        if last_used is not None and last_used.tzinfo is None:
            last_used = last_used.replace(tzinfo=timezone.utc)
        if last_used is None or (now - last_used).total_seconds() > 60:  # avoid a write per request
            key.last_used_at = now
            db.commit()
        # Request handlers may use this tenant-scoped ID to queue subscribed workspace
        # webhooks; never derive tenant identity from caller-supplied headers.
        request.state.customer_organization_id = key.organization_id
        return _customer_rate_limit_identity(key.organization_id)

def _check_nonce_local(nonce, expires_at):
    now=time.time()
    with _nonce_lock:
        for key, expiry in list(_seen_nonces.items()):
            if expiry <= now: _seen_nonces.pop(key,None)
        if nonce in _seen_nonces: return False
        _seen_nonces[nonce]=expires_at
        return True

async def _check_nonce(nonce, ttl):
    client=_redis_client()
    nonce_key='registry:hmac:nonce:'+hashlib.sha256(nonce.encode()).hexdigest()
    if client is not None:
        try: return bool(await asyncio.to_thread(client.set,nonce_key,'1',nx=True,ex=ttl))
        except Exception:
            if settings.require_hmac: raise HTTPException(503,'Replay protection is temporarily unavailable')
    return _check_nonce_local(nonce_key,time.time()+ttl)

async def _take_token(identity, request):
    capacity=max(1,settings.registry_rate_limit_capacity)
    refill=max(0.01,settings.registry_rate_limit_refill_per_second)
    client=_redis_client(); client_key=hashlib.sha256(identity.encode()).hexdigest()
    key='registry:rate:'+client_key; ttl=max(60,int((capacity/refill)*2))
    if client is not None:
        try:
            allowed=await asyncio.to_thread(client.eval,_TOKEN_BUCKET_LUA,1,key,capacity,refill,time.time(),ttl)
            if not allowed: raise HTTPException(429,'Registry lookup rate limit exceeded',headers={'Retry-After':'1'})
            return
        except HTTPException: raise
        except Exception:
            if settings.app_env.lower()=='production' and settings.redis_url:
                raise HTTPException(503,'Distributed rate limiter is unavailable')
    now=time.monotonic()
    with _bucket_lock:
        tokens,last=_local_buckets.get(key,(float(capacity),now))
        tokens=min(float(capacity),tokens+max(0.0,now-last)*refill)
        if tokens<1:
            _local_buckets[key]=(tokens,now)
            raise HTTPException(429,'Registry lookup rate limit exceeded',headers={'Retry-After':'1'})
        _local_buckets[key]=(tokens-1,now)

RATE_LIMITED_LOOKUP_PATHS = frozenset({
    "/api/v1/registry/lookup",
    "/api/v1/registry/search",
    "/api/v1/organizations",
})


def requires_lookup_rate_limit(path: str) -> bool:
    """Paths that can reveal or enumerate canonical registry records."""
    return path in RATE_LIMITED_LOOKUP_PATHS


def is_customer_identity(identity):
    return str(identity).startswith("customer-api-key:")

async def _read_bounded_body(request):
    """Buffer the body for HMAC verification without accepting unbounded uploads."""
    limit=settings.max_upload_bytes+1024*1024
    declared=request.headers.get('content-length')
    if declared and declared.isdigit() and int(declared)>limit:
        raise HTTPException(413,'Request body exceeds the configured limit')
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>limit: raise HTTPException(413,'Request body exceeds the configured limit')
        chunks.append(chunk)
    body=b''.join(chunks)
    request._body=body  # let downstream form parsing reuse the verified bytes
    return body

async def require_api_key(request:Request,
    x_api_key:str|None=Header(default=None,alias='X-API-Key'),
    x_internal_signature:str|None=Header(default=None,alias='X-Internal-Signature'),
    x_internal_timestamp:str|None=Header(default=None,alias='X-Internal-Timestamp'),
    x_internal_nonce:str|None=Header(default=None,alias='X-Internal-Nonce')):
    if x_internal_signature is not None:
        secret=settings.hmac_shared_secret
        if not secret or not x_internal_timestamp or not x_internal_nonce:
            raise HTTPException(401,'Invalid internal signature headers')
        try: timestamp=int(x_internal_timestamp)
        except (TypeError,ValueError): raise HTTPException(401,'Invalid internal signature timestamp')
        if abs(time.time()-timestamp)>max(30,settings.hmac_clock_skew_seconds):
            raise HTTPException(401,'Internal signature timestamp expired')
        if not x_internal_nonce or len(x_internal_nonce)>200:
            raise HTTPException(401,'Invalid internal signature nonce')
        body=await _read_bounded_body(request); body_hash=hashlib.sha256(body).hexdigest()
        canonical='\n'.join([str(timestamp),x_internal_nonce,request.method.upper(),request.url.path,request.url.query,body_hash])
        expected=hmac.new(secret.encode(),canonical.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,x_internal_signature.lower()):
            raise HTTPException(401,'Invalid internal signature')
        if not await _check_nonce(x_internal_nonce,max(60,settings.hmac_nonce_ttl_seconds)):
            raise HTTPException(401,'Internal request replay detected')
        identity='hmac-client:'+(request.client.host if request.client else 'unknown')
    elif not x_api_key:
        from .admin_auth import session_from_request,enforce_session_csrf
        claims=session_from_request(request)
        if not claims: raise HTTPException(401,'Invalid or missing API key')
        enforce_session_csrf(request,claims)
        identity='admin-session:'+str(claims.get('sub','admin'))
    else:
        if x_api_key.startswith(("pg_sandbox_","pg_live_")):
            identity=await asyncio.to_thread(_validate_customer_api_key,x_api_key,request)
        else:
            if settings.require_hmac: raise HTTPException(401,'Signed internal request required')
            keys=settings.api_key_list
            if not keys or not any(hmac.compare_digest(x_api_key,key) for key in keys):
                raise HTTPException(401,'Invalid or missing API key')
            identity='api-key:'+hashlib.sha256(x_api_key.encode()).hexdigest()
    if requires_lookup_rate_limit(request.url.path):
        await _take_token(identity,request)
    return identity
