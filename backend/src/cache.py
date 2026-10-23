"""Best-effort Redis cache for registry lookup responses; database remains authoritative."""
import json
from functools import lru_cache
from redis import Redis
from prometheus_client import Counter

CACHE_REQUESTS=Counter('registry_cache_requests_total','Registry cache operations by result',['result'])
from .config import settings

@lru_cache(maxsize=1)
def _client():
    if not settings.redis_url:
        return None
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)

def get_json(key):
    client = _client()
    if client is None:
        CACHE_REQUESTS.labels('bypass').inc()
        return None
    try:
        raw = client.get(key)
        CACHE_REQUESTS.labels('hit' if raw is not None else 'miss').inc()
        return json.loads(raw) if raw is not None else None
    except Exception:
        CACHE_REQUESTS.labels('error').inc()
        return None

def set_json(key, value, ttl_seconds):
    client = _client()
    if client is None:
        return False
    try:
        client.set(key, json.dumps(value, separators=(',', ':'), ensure_ascii=False), ex=max(1, int(ttl_seconds)))
        return True
    except Exception:
        return False

def invalidate_lookup_keys(keys):
    client = _client()
    if client is None or not keys:
        return 0
    try:
        return int(client.delete(*list(keys)))
    except Exception:
        return 0
