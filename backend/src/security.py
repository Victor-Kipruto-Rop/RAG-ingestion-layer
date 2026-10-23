import asyncio
import hashlib
import hmac
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from fastapi import Header, HTTPException, Request
from redis import Redis
from sqlalchemy import select
from .config import settings
from .database import SessionLocal
from .models import ApiKey, ApiKeySecurityEvent

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

def _check_nonce_local(nonce, expires_at):
    now = time.time()
    with _nonce_lock:
        for key, expiry in list(_seen_nonces.items()):
            if expiry <= now:
                _seen_nonces.pop(key, None)
        if nonce in _seen_nonces:
            return False
        _seen_nonces[nonce] = expires_at
        return True

async def _check_nonce(nonce, ttl):
    client = _redis_client()
    nonce_key = 'registry:hmac:nonce:' + hashlib.sha256(nonce.encode()).hexdigest()
    if client is not None:
        try:
            return bool(await asyncio.to_thread(client.set, nonce_key, '1', nx=True, ex=ttl))
        except Exception:
            if settings.require_hmac:
                raise HTTPException(503, 'Replay protection is temporarily unavailable')
    return _check_nonce_local(nonce_key, time.time() + ttl)

async def _take_token(identity, request):
    capacity = max(1, settings.registry_rate_limit_capacity)
    refill = max(0.01, settings.registry_rate_limit_refill_per_second)
    client = _redis_client()
    client_key = hashlib.sha256(identity.encode()).hexdigest()
    key = 'registry:rate:' + client_key
    ttl = max(60, int((capacity / refill) * 2))
    if client is not None:
        try:
            allowed = await asyncio.to_thread(client.eval, _TOKEN_BUCKET_LUA, 1, key, capacity, refill, time.time(), ttl)
            if not allowed:
                raise HTTPException(429, 'Registry lookup rate limit exceeded', headers={'Retry-After': '1'})
            return
        except HTTPException:
            raise
        except Exception:
            if settings.app_env.lower() == 'production' and settings.redis_url:
                raise HTTPException(503, 'Distributed rate limiter is unavailable')
    now = time.monotonic()
    with _bucket_lock:
        tokens, last = _local_buckets.get(key, (float(capacity), now))
        tokens = min(float(capacity), tokens + max(0.0, now - last) * refill)
        if tokens < 1:
            _local_buckets[key] = (tokens, now)
            raise HTTPException(429, 'Registry lookup rate limit exceeded', headers={'Retry-After': '1'})
        _local_buckets[key] = (tokens - 1, now)

def _managed_key(raw_key: str, request: Request):
    # Recognizable managed-key prefixes never fall back to legacy shared-key auth.
    if raw_key.startswith('pg_sandbox_'):
        prefix = 'pg_sandbox_' + raw_key[len('pg_sandbox_'):len('pg_sandbox_') + 8]
    elif raw_key.startswith('pg_live_'):
        prefix = 'pg_live_' + raw_key[len('pg_live_'):len('pg_live_') + 8]
    else:
        return None
    digest = hashlib.sha256(raw_key.encode()).hexdigest()
    with SessionLocal() as db:
        row = db.scalar(select(ApiKey).where(ApiKey.key_prefix == prefix))
        if not row or not hmac.compare_digest(row.secret_hash, digest):
            raise HTTPException(401, 'Invalid or missing API key')
        expires_at = row.expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if row.status != 'active' or (expires_at and expires_at <= datetime.now(timezone.utc)):
            raise HTTPException(401, 'API key is revoked or expired')
        expected_environment = settings.pesaguard_datasource_environment
        if row.environment != expected_environment:
            request_id = getattr(request.state, 'request_id', None) or request.headers.get('X-Correlation-ID')
            db.add(ApiKeySecurityEvent(
                api_key_id=row.id, key_prefix=prefix, event_type='environment_mismatch',
                expected_environment=expected_environment, key_environment=row.environment,
                endpoint=request.url.path[:300], request_id=request_id,
                source_ip=request.client.host if request.client else None,
                details={'method': request.method},
            ))
            db.commit()
            raise HTTPException(403, detail={'code':'API_KEY_ENVIRONMENT_MISMATCH',
              'message':f'This API key is for {row.environment} only. Use a {expected_environment} key for this environment.'})
        scopes = row.scopes if isinstance(row.scopes, list) else []
        path = request.url.path
        if path == '/api/v1/ingestion/preview':
            needed = 'registry:read'
        elif request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            needed = 'sources:write' if path.startswith('/api/v1/sources') else 'registry:write'
        elif path.startswith('/api/v1/exports/'):
            needed = 'exports:read'
        else:
            needed = 'registry:read'
        if needed not in scopes:
            raise HTTPException(403, detail={'code':'API_KEY_SCOPE_INSUFFICIENT','message':f'This key requires the {needed} scope.'})
        row.last_used_at = datetime.now(timezone.utc)
        db.commit()
        request.state.api_key_id = row.id
        request.state.api_key_prefix = prefix
        request.state.api_key_environment = row.environment
        return 'managed-api-key:' + row.id

async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias='X-API-Key'),
    x_internal_signature: str | None = Header(default=None, alias='X-Internal-Signature'),
    x_internal_timestamp: str | None = Header(default=None, alias='X-Internal-Timestamp'),
    x_internal_nonce: str | None = Header(default=None, alias='X-Internal-Nonce'),
):
    if x_internal_signature is not None:
        secret = settings.hmac_shared_secret
        if not secret or not x_internal_timestamp or not x_internal_nonce:
            raise HTTPException(401, 'Invalid internal signature headers')
        try:
            timestamp = int(x_internal_timestamp)
        except (TypeError, ValueError):
            raise HTTPException(401, 'Invalid internal signature timestamp')
        if abs(time.time() - timestamp) > max(30, settings.hmac_clock_skew_seconds):
            raise HTTPException(401, 'Internal signature timestamp expired')
        if not x_internal_nonce or len(x_internal_nonce) > 200:
            raise HTTPException(401, 'Invalid internal signature nonce')
        body = await request.body()
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = '\n'.join([str(timestamp), x_internal_nonce, request.method.upper(), request.url.path, request.url.query, body_hash])
        expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_internal_signature.lower()):
            raise HTTPException(401, 'Invalid internal signature')
        if not await _check_nonce(x_internal_nonce, max(60, settings.hmac_nonce_ttl_seconds)):
            raise HTTPException(401, 'Internal request replay detected')
        identity = 'hmac-client:' + (request.client.host if request.client else 'unknown')
    else:
        if settings.require_hmac:
            raise HTTPException(401, 'Signed internal request required')
        if not x_api_key:
            raise HTTPException(401, 'Invalid or missing API key')
        if x_api_key.startswith(("pg_sandbox_", "pg_live_")):
            identity = _managed_key(x_api_key, request)
        else:
            keys = settings.api_key_list
            if not keys:
                raise HTTPException(503, 'Service authentication is not configured')
            if not any(hmac.compare_digest(x_api_key, key) for key in keys):
                raise HTTPException(401, 'Invalid or missing API key')
            identity = 'api-key:' + hashlib.sha256(x_api_key.encode()).hexdigest()
    if request.url.path in {'/api/v1/registry/lookup', '/api/v1/registry/search'}:
        await _take_token(identity, request)
    return identity
