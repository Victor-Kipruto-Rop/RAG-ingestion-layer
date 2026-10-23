from types import SimpleNamespace
import hashlib
from src.key_management import new_key, ALLOWED_SCOPES
from src.security import _effective_environment, _required_scope
from src.config import settings

def test_sandbox_key_has_environment_specific_prefix_and_hash_only_material():
    prefix, secret, digest = new_key('sandbox')
    assert prefix.startswith('pg_sandbox_')
    assert secret.startswith(prefix + '_')
    assert len(digest) == 64
    assert digest == hashlib.sha256(secret.encode()).hexdigest()
    assert secret != digest

def test_production_key_has_live_prefix():
    prefix, secret, digest = new_key('production')
    assert prefix.startswith('pg_live_')
    assert secret.startswith(prefix + '_')
    assert digest == hashlib.sha256(secret.encode()).hexdigest()

def test_supported_scopes_are_explicit():
    assert ALLOWED_SCOPES == {'registry:read', 'ingestion:write', 'sources:write', 'exports:read'}

def test_environment_uses_server_configuration(monkeypatch):
    monkeypatch.setattr(settings, 'datasource_environment', 'production')
    monkeypatch.setattr(settings, 'app_env', 'development')
    assert _effective_environment() == 'production'
    monkeypatch.setattr(settings, 'datasource_environment', '')
    monkeypatch.setattr(settings, 'app_env', 'production')
    assert _effective_environment() == 'production'
    monkeypatch.setattr(settings, 'app_env', 'development')
    assert _effective_environment() == 'sandbox'

def test_scope_mapping_for_sensitive_routes():
    request = SimpleNamespace(url=SimpleNamespace(path='/api/v1/ingestion/uploads'), method='POST')
    assert _required_scope(request) == 'ingestion:write'
    request = SimpleNamespace(url=SimpleNamespace(path='/api/v1/exports/organizations.csv'), method='GET')
    assert _required_scope(request) == 'exports:read'
    request = SimpleNamespace(url=SimpleNamespace(path='/api/v1/quality/summary'), method='GET')
    assert _required_scope(request) == 'registry:read'
    request = SimpleNamespace(url=SimpleNamespace(path='/api/v1/warehouse/query-organization'), method='GET')
    assert _required_scope(request) == 'registry:read'


def test_managed_key_prefix_never_falls_back_to_legacy_auth(monkeypatch):
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from src.security import require_api_key

    app = FastAPI()

    @app.get('/protected')
    async def protected(identity=Depends(require_api_key)):
        return {'identity': identity}

    # A managed-looking key must not be accepted as a legacy key when managed
    # key support is disabled, even if it is accidentally placed in the allowlist.
    monkeypatch.setattr(settings, 'managed_api_keys_enabled', False)
    monkeypatch.setattr(settings, 'require_hmac', False)
    monkeypatch.setattr(settings, 'registry_api_keys', 'pg_sandbox_example_secret')
    response = TestClient(app).get('/protected', headers={'X-API-Key': 'pg_sandbox_example_secret'})
    assert response.status_code == 503
    assert 'cannot fall back' in response.json()['detail'].lower()
