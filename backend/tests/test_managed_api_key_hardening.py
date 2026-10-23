import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src import key_management, security


def request_for(path="/api/v1/registry/search", method="GET"):
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "https", "path": path, "raw_path": path.encode(),
        "query_string": b"", "headers": [], "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    }
    request = Request(scope)
    request.state.request_id = "test-request-1"
    return request


@pytest.mark.parametrize(("environment", "marker"), [
    ("sandbox", "pg_sandbox_"), ("production", "pg_live_"),
])
def test_generated_key_is_environment_scoped_and_only_hash_is_stored(environment, marker):
    prefix, secret, digest = key_management.new_key(environment)
    assert prefix.startswith(marker)
    assert secret.startswith(prefix + "_")
    assert digest != secret
    assert digest == hashlib.sha256(secret.encode()).hexdigest()
    assert len(digest) == 64


def test_generated_keys_are_unique():
    first = key_management.new_key("sandbox")
    second = key_management.new_key("sandbox")
    assert first[0] != second[0]
    assert first[1] != second[1]
    assert first[2] != second[2]


def test_admin_auth_fails_closed_without_server_token(monkeypatch):
    monkeypatch.setattr(key_management.settings, "datasource_admin_token", "")
    with pytest.raises(HTTPException) as exc:
        key_management.require_admin_token()
    assert exc.value.status_code == 503


def test_admin_auth_rejects_wrong_token(monkeypatch):
    monkeypatch.setattr(key_management.settings, "datasource_admin_token", "expected")
    with pytest.raises(HTTPException) as exc:
        key_management.require_admin_token("Bearer incorrect")
    assert exc.value.status_code == 401


@pytest.mark.parametrize(("deployment", "key_environment", "raw_key"), [
    ("production", "sandbox", "pg_sandbox_publicid_secret"),
    ("sandbox", "production", "pg_live_publicid_secret"),
])
@pytest.mark.asyncio
async def test_key_environment_mismatch_is_rejected_and_audited(
    monkeypatch, deployment, key_environment, raw_key
):
    events = []
    monkeypatch.setattr(security.settings, "datasource_environment", deployment)
    monkeypatch.setattr(security.settings, "app_env", "production" if deployment == "production" else "development")
    monkeypatch.setattr(security.settings, "managed_api_keys_enabled", True)
    monkeypatch.setattr(security, "_managed_key_from_db", lambda supplied: {
        "id": "key-1", "key_prefix": supplied.rsplit("_", 1)[0],
        "environment": key_environment, "scopes": ["registry:read"],
    })
    monkeypatch.setattr(security, "_record_security_event", lambda request, event_type, key=None, key_environment=None, details=None:
                        events.append((event_type, key_environment, details)))

    with pytest.raises(HTTPException) as exc:
        await security.require_api_key(request_for(), x_api_key=raw_key)
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert events and events[0][0] == "environment_mismatch"


@pytest.mark.asyncio
async def test_missing_scope_is_rejected_and_audited(monkeypatch):
    events = []
    monkeypatch.setattr(security.settings, "datasource_environment", "sandbox")
    monkeypatch.setattr(security.settings, "app_env", "development")
    monkeypatch.setattr(security.settings, "managed_api_keys_enabled", True)
    monkeypatch.setattr(security, "_managed_key_from_db", lambda supplied: {
        "id": "key-1", "key_prefix": "pg_sandbox_publicid",
        "environment": "sandbox", "scopes": ["registry:read"],
    })
    monkeypatch.setattr(security, "_record_security_event", lambda request, event_type, key=None, key_environment=None, details=None:
                        events.append((event_type, details)))

    with pytest.raises(HTTPException) as exc:
        await security.require_api_key(request_for("/api/v1/ingestion/uploads", "POST"),
                                       x_api_key="pg_sandbox_publicid_secret")
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "API_KEY_SCOPE_DENIED"
    assert events[0][0] == "scope_denied"
    assert events[0][1]["required_scope"] == "ingestion:write"


def test_key_is_invalid_when_prefix_and_database_environment_disagree(monkeypatch):
    class FakeDB:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def scalar(self, statement):
            return SimpleNamespace(
                secret_hash=hashlib.sha256(b"pg_sandbox_publicid_secret").hexdigest(),
                environment="production", expires_at=None, status="active",
                id="key-1", key_prefix="pg_sandbox_publicid",
                scopes=["registry:read"], last_used_at=None,
            )
        def commit(self): pass

    monkeypatch.setattr(security, "SessionLocal", lambda: FakeDB())
    assert security._managed_key_from_db("pg_sandbox_publicid_secret") is None
