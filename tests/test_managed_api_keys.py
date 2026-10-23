import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src import key_management, security
from src.config import settings


def request_for(path="/api/v1/registry/lookup", method="GET"):
    return Request({
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "server": ("datasource.test", 443),
        "client": ("127.0.0.1", 50000),
    })


def test_new_key_is_environment_prefixed_and_only_digest_is_returned():
    for environment, prefix_start in (("sandbox", "pg_sandbox_"), ("production", "pg_live_")):
        prefix, secret, digest = key_management.new_key(environment)
        assert prefix.startswith(prefix_start)
        assert secret.startswith(prefix + "_")
        assert len(digest) == 64
        assert digest != secret
        assert secret.split("_", 3)[-1]


def test_required_scope_maps_write_and_read_routes():
    assert security._required_scope(request_for("/api/v1/ingestion/uploads", "POST")) == "ingestion:write"
    assert security._required_scope(request_for("/api/v1/registry/lookup", "GET")) == "registry:read"
    assert security._required_scope(request_for("/api/v1/exports/organizations.csv", "GET")) == "exports:read"
    assert security._required_scope(request_for("/api/v1/sources", "POST")) == "sources:write"


def test_deployment_environment_prefers_explicit_datasource_environment(monkeypatch):
    monkeypatch.setattr(settings, "datasource_environment", "production")
    monkeypatch.setattr(settings, "app_env", "development")
    assert security._effective_environment() == "production"


def test_managed_sandbox_key_is_rejected_in_production_and_logged(monkeypatch):
    events = []
    monkeypatch.setattr(settings, "managed_api_keys_enabled", True)
    monkeypatch.setattr(security, "_managed_key_from_db", lambda raw: {
        "id": "key-id", "key_prefix": "pg_sandbox_abc123", "environment": "sandbox",
        "scopes": ["registry:read"],
    })
    monkeypatch.setattr(security, "_effective_environment", lambda: "production")
    monkeypatch.setattr(security, "_record_security_event", lambda *args, **kwargs: events.append((args, kwargs)))

    with pytest.raises(HTTPException) as caught:
        asyncio.run(security.require_api_key(request_for(), x_api_key="pg_sandbox_abc123_secret"))

    assert caught.value.status_code == 403
    assert caught.value.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert "sandbox" in caught.value.detail["message"]
    assert events
    assert events[0][0][1] == "environment_mismatch"


def test_managed_key_without_required_scope_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "managed_api_keys_enabled", True)
    monkeypatch.setattr(security, "_managed_key_from_db", lambda raw: {
        "id": "key-id", "key_prefix": "pg_sandbox_abc123", "environment": "sandbox",
        "scopes": ["registry:read"],
    })
    monkeypatch.setattr(security, "_effective_environment", lambda: "sandbox")
    monkeypatch.setattr(security, "_record_security_event", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as caught:
        asyncio.run(security.require_api_key(request_for("/api/v1/ingestion/uploads", "POST"), x_api_key="pg_sandbox_abc123_secret"))

    assert caught.value.status_code == 403
    assert caught.value.detail["code"] == "API_KEY_SCOPE_DENIED"


def test_admin_token_is_required_and_compared_constant_time(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "a-long-test-admin-token")
    assert key_management.require_admin_token("Bearer a-long-test-admin-token") == "operator"
    with pytest.raises(HTTPException) as caught:
        key_management.require_admin_token("Bearer wrong-token")
    assert caught.value.status_code == 401
