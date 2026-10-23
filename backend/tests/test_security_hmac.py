import hashlib
import hmac
import time

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.config import settings
from src.security import require_api_key, _redis_client, _seen_nonces, _local_buckets


def make_app():
    app = FastAPI()

    @app.get('/protected')
    async def protected(identity=Depends(require_api_key)):
        return {'identity': identity}

    return app


def signed_headers(method, path, query='', body=b'', nonce='test-nonce'):
    timestamp = str(int(time.time()))
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = '\n'.join([timestamp, nonce, method.upper(), path, query, body_hash])
    signature = hmac.new(settings.hmac_shared_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {'X-Internal-Timestamp': timestamp, 'X-Internal-Nonce': nonce, 'X-Internal-Signature': signature}


def test_hmac_signed_request_succeeds_and_replay_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, 'hmac_shared_secret', 'unit-test-secret')
    monkeypatch.setattr(settings, 'require_hmac', True)
    monkeypatch.setattr(settings, 'redis_url', '')
    monkeypatch.setattr(settings, 'registry_rate_limit_capacity', 100)
    _redis_client.cache_clear()
    _seen_nonces.clear()
    _local_buckets.clear()
    client = TestClient(make_app())
    headers = signed_headers('GET', '/protected', nonce='nonce-hmac-test-001')
    assert client.get('/protected', headers=headers).status_code == 200
    replay = client.get('/protected', headers=headers)
    assert replay.status_code == 401
    assert 'replay' in replay.json()['detail'].lower()


def test_invalid_hmac_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, 'hmac_shared_secret', 'unit-test-secret')
    monkeypatch.setattr(settings, 'require_hmac', False)
    monkeypatch.setattr(settings, 'redis_url', '')
    _redis_client.cache_clear()
    client = TestClient(make_app())
    headers = signed_headers('GET', '/protected', nonce='nonce-hmac-test-002')
    headers['X-Internal-Signature'] = '0' * 64
    assert client.get('/protected', headers=headers).status_code == 401


def test_api_key_compatibility_remains_available_during_rollout(monkeypatch):
    monkeypatch.setattr(settings, 'require_hmac', False)
    monkeypatch.setattr(settings, 'registry_api_keys', 'legacy-test-key')
    _local_buckets.clear()
    client = TestClient(make_app())
    assert client.get('/protected', headers={'X-API-Key': 'legacy-test-key'}).status_code == 200
    assert client.get('/protected', headers={'X-API-Key': 'wrong'}).status_code == 401
