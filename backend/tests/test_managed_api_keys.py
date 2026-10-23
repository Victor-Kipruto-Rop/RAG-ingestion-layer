from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import settings
from src.api_keys import router as api_keys_router
from src.database import Base, get_db
from src.managed_keys import APIKeySecurityEvent, ManagedAPIKey, issue_key, key_public
from src.security import require_api_key


def test_sandbox_key_is_rejected_by_production_and_event_is_logged(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr("src.managed_keys.SessionLocal", TestingSession)
    monkeypatch.setattr(settings, "datasource_environment", "production")
    monkeypatch.setattr(settings, "registry_api_keys", "")
    issued = issue_key("sandbox test", "sandbox", ["registry:read"], 90)
    with TestingSession() as db:
        db.add(ManagedAPIKey(**{k: v for k, v in issued.items() if k != "secret"}))
        db.commit()

    app = FastAPI()

    @app.get("/api/v1/registry/lookup")
    async def protected(identity=Depends(require_api_key)):
        return {"ok": True}

    response = TestClient(app).get("/api/v1/registry/lookup", headers={"X-API-Key": issued["secret"]})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    with TestingSession() as db:
        event = db.query(APIKeySecurityEvent).filter_by(event_type="environment_mismatch").one()
        assert event.requested_environment == "production"


def test_production_key_succeeds_in_production_and_scopes_are_enforced(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr("src.managed_keys.SessionLocal", TestingSession)
    monkeypatch.setattr(settings, "datasource_environment", "production")
    monkeypatch.setattr(settings, "registry_api_keys", "")
    issued = issue_key("production read", "production", ["registry:read"], 90)
    with TestingSession() as db:
        db.add(ManagedAPIKey(**{k: v for k, v in issued.items() if k != "secret"}))
        db.commit()

    app = FastAPI()

    @app.get("/api/v1/registry/lookup")
    async def lookup(identity=Depends(require_api_key)):
        return {"ok": True}

    @app.post("/api/v1/ingestion/uploads")
    async def upload(identity=Depends(require_api_key)):
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/v1/registry/lookup", headers={"X-API-Key": issued["secret"]}).status_code == 200
    denied = client.post("/api/v1/ingestion/uploads", headers={"X-API-Key": issued["secret"]})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "API_KEY_SCOPE_DENIED"


def test_key_public_serializer_never_exposes_secret_or_hash():
    issued = issue_key("test", "sandbox", ["registry:read"], 30)
    key = ManagedAPIKey(**{k: v for k, v in issued.items() if k != "secret"})
    payload = key_public(key)
    assert "secret" not in payload
    assert "key_hash" not in payload
    assert issued["secret"] not in str(payload)



def test_operator_can_create_list_and_revoke_key_without_revealing_secret(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        with TestingSession() as db:
            yield db

    monkeypatch.setattr("src.managed_keys.SessionLocal", TestingSession)
    monkeypatch.setattr(settings, "key_management_token", "test-only-management-token")
    monkeypatch.setattr(settings, "datasource_environment", "development")
    monkeypatch.setattr(settings, "registry_api_keys", "")

    app = FastAPI()
    app.include_router(api_keys_router)
    app.dependency_overrides[get_db] = override_db

    client = TestClient(app)
    headers = {"X-Key-Management-Token": "test-only-management-token"}
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=headers,
        json={
            "name": "Sandbox test key",
            "environment": "sandbox",
            "scopes": ["registry:read"],
            "expires_in_days": 30,
        },
    )
    assert created.status_code == 201
    payload = created.json()
    secret = payload["secret"]
    key_id = payload["key"]["id"]
    assert secret.startswith("pg_sandbox_")
    assert "key_hash" not in payload["key"]

    listed = client.get("/api/v1/admin/api-keys?environment=sandbox", headers=headers)
    assert listed.status_code == 200
    assert secret not in listed.text
    assert listed.json()["count"] == 1

    revoked = client.post(f"/api/v1/admin/api-keys/{key_id}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["key"]["status"] == "revoked"
