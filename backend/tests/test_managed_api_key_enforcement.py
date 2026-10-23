from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src import security
from src.config import settings


def make_app():
    app = FastAPI()

    @app.get("/api/v1/registry/lookup")
    async def lookup(identity=Depends(security.require_api_key)):
        return {"identity": identity}

    @app.post("/api/v1/sources")
    async def create_source(identity=Depends(security.require_api_key)):
        return {"identity": identity}

    return app


def configure(monkeypatch, environment="production"):
    monkeypatch.setattr(settings, "datasource_environment", environment)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "managed_api_keys_enabled", True)
    monkeypatch.setattr(settings, "require_hmac", False)
    monkeypatch.setattr(settings, "registry_api_keys", "")
    events = []
    monkeypatch.setattr(security, "_record_security_event",
                        lambda request, event_type, key=None, key_environment=None, details=None:
                        events.append({"type": event_type, "key": key, "key_environment": key_environment, "details": details or {}}))
    return events


def test_sandbox_key_is_rejected_by_production_and_security_event_recorded(monkeypatch):
    events = configure(monkeypatch, "production")
    monkeypatch.setattr(security, "_managed_key_from_db", lambda raw: {
        "id": "key-1", "key_prefix": "pg_sandbox_abc123", "environment": "sandbox", "scopes": ["registry:read"]
    })
    client = TestClient(make_app())

    response = client.get("/api/v1/registry/lookup?reg_no=TEST",
                          headers={"X-API-Key": "pg_sandbox_abc123_secret",
                                   "X-Datasource-Environment": "sandbox"})

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert "only be used with the sandbox datasource environment" in detail["message"]
    assert events and events[0]["type"] == "environment_mismatch"
    assert events[0]["key_environment"] == "sandbox"


def test_matching_managed_key_environment_is_allowed(monkeypatch):
    configure(monkeypatch, "sandbox")
    monkeypatch.setattr(security, "_managed_key_from_db", lambda raw: {
        "id": "key-2", "key_prefix": "pg_sandbox_abc123", "environment": "sandbox", "scopes": ["registry:read"]
    })
    response = TestClient(make_app()).get("/api/v1/registry/lookup?reg_no=TEST",
                                          headers={"X-API-Key": "pg_sandbox_abc123_secret"})
    assert response.status_code == 200


def test_missing_scope_is_denied_and_recorded(monkeypatch):
    events = configure(monkeypatch, "production")
    monkeypatch.setattr(security, "_managed_key_from_db", lambda raw: {
        "id": "key-3", "key_prefix": "pg_live_abc123", "environment": "production", "scopes": ["registry:read"]
    })
    response = TestClient(make_app()).post("/api/v1/sources",
                                           headers={"X-API-Key": "pg_live_abc123_secret"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_SCOPE_DENIED"
    assert events and events[0]["type"] == "scope_denied"
