"""Focused contract tests for environment isolation helpers."""
import hashlib
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models import ApiKey


def test_api_key_model_does_not_need_plaintext_secret():
    key = ApiKey(
        id="id-1", organization_id="org-1", created_by_user_id="user-1",
        name="Sandbox", environment="sandbox", key_prefix="pg_sandbox_abcd",
        secret_hash=hashlib.sha256(b"example").hexdigest(), scopes=["registry:read"],
        status="active", created_at=datetime.now(timezone.utc),
    )
    assert not hasattr(key, "secret")
    assert key.environment == "sandbox"
    assert len(key.secret_hash) == 64


def test_environment_mismatch_error_message_contract():
    from src.security import environment_mismatch_detail
    detail = environment_mismatch_detail("sandbox", "production")
    assert detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert "sandbox environment" in detail["message"].lower()
    assert detail["key_environment"] == "sandbox"
    assert detail["requested_environment"] == "production"


def test_sandbox_key_prefix_is_detectable_without_shared_registry():
    from src.security import environment_mismatch_detail
    response = environment_mismatch_detail("sandbox", "production")
    assert response["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert response["key_environment"] == "sandbox"
    assert response["requested_environment"] == "production"


def test_sandbox_key_is_rejected_and_flagged_on_production(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from src import security

    class FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def scalar(self, statement):
            return None

    events = []
    monkeypatch.setattr(security.settings, "api_environment", "production")
    monkeypatch.setattr(security, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(security, "_audit_unknown_environment_mismatch",
                        lambda *args: events.append(args))
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/v1/registry/lookup"),
        state=SimpleNamespace(request_id="test-request"),
        client=SimpleNamespace(host="127.0.0.1"),
    )
    with pytest.raises(HTTPException) as raised:
        security._validate_customer_api_key("pg_sandbox_fake-secret", request)
    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert raised.value.detail["key_environment"] == "sandbox"
    assert events, "environment mismatch should create a security audit event"


def test_production_key_is_rejected_on_sandbox(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from src import security

    class FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def scalar(self, statement):
            return None

    events = []
    monkeypatch.setattr(security.settings, "api_environment", "sandbox")
    monkeypatch.setattr(security, "SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(security, "_audit_unknown_environment_mismatch",
                        lambda *args: events.append(args))
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/v1/registry/lookup"),
        state=SimpleNamespace(request_id="test-request"),
        client=SimpleNamespace(host="127.0.0.1"),
    )
    with pytest.raises(HTTPException) as raised:
        security._validate_customer_api_key("pg_live_fake-secret", request)
    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert raised.value.detail["requested_environment"] == "sandbox"
    assert events
