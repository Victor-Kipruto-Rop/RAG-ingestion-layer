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


def test_managed_sandbox_key_is_rejected_in_production_and_logged(monkeypatch):
    import asyncio
    import pytest
    from fastapi import HTTPException
    from starlette.requests import Request
    from src import security

    events = []
    monkeypatch.setattr(settings, 'managed_api_keys_enabled', True)
    monkeypatch.setattr(security, '_managed_key_from_db', lambda raw: {
        'id': 'key-id', 'key_prefix': 'pg_sandbox_abc123',
        'environment': 'sandbox', 'scopes': ['registry:read'],
    })
    monkeypatch.setattr(security, '_effective_environment', lambda: 'production')
    monkeypatch.setattr(security, '_record_security_event', lambda *args, **kwargs: events.append((args, kwargs)))

    path = '/api/v1/registry/lookup'
    request = Request({
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'GET', 'scheme': 'https', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'root_path': '', 'headers': [],
        'server': ('datasource.test', 443), 'client': ('127.0.0.1', 50000),
    })
    with pytest.raises(HTTPException) as caught:
        asyncio.run(security.require_api_key(request, x_api_key='pg_sandbox_abc123_secret'))

    assert caught.value.status_code == 403
    assert caught.value.detail['code'] == 'API_KEY_ENVIRONMENT_MISMATCH'
    assert 'sandbox' in caught.value.detail['message']
    assert events and events[0][0][1] == 'environment_mismatch'


def test_managed_key_without_required_scope_is_rejected(monkeypatch):
    import asyncio
    import pytest
    from fastapi import HTTPException
    from starlette.requests import Request
    from src import security

    monkeypatch.setattr(settings, 'managed_api_keys_enabled', True)
    monkeypatch.setattr(security, '_managed_key_from_db', lambda raw: {
        'id': 'key-id', 'key_prefix': 'pg_sandbox_abc123',
        'environment': 'sandbox', 'scopes': ['registry:read'],
    })
    monkeypatch.setattr(security, '_effective_environment', lambda: 'sandbox')
    monkeypatch.setattr(security, '_record_security_event', lambda *args, **kwargs: None)

    path = '/api/v1/ingestion/uploads'
    request = Request({
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
        'method': 'POST', 'scheme': 'https', 'path': path, 'raw_path': path.encode(),
        'query_string': b'', 'root_path': '', 'headers': [],
        'server': ('datasource.test', 443), 'client': ('127.0.0.1', 50000),
    })
    with pytest.raises(HTTPException) as caught:
        asyncio.run(security.require_api_key(request, x_api_key='pg_sandbox_abc123_secret'))

    assert caught.value.status_code == 403
    assert caught.value.detail['code'] == 'API_KEY_SCOPE_DENIED'
