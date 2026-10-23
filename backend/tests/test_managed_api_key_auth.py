from datetime import datetime, timezone, timedelta

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src import security
from src.database import Base
from src.key_management import new_key
from src.models import APIKeySecurityEvent, ManagedAPIKey
from src.config import settings


def make_test_client(monkeypatch, environment="production"):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(security, "SessionLocal", factory)
    monkeypatch.setattr(settings, "datasource_environment", environment)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "managed_api_keys_enabled", True)
    monkeypatch.setattr(settings, "require_hmac", False)
    monkeypatch.setattr(settings, "registry_api_keys", "")
    security._local_buckets.clear()

    app = FastAPI()

    @app.get("/protected")
    async def protected(identity=Depends(security.require_api_key)):
        return {"identity": identity}

    @app.post("/api/v1/ingestion/uploads")
    async def upload(identity=Depends(security.require_api_key)):
        return {"identity": identity}

    return TestClient(app), engine, factory


def insert_key(factory, environment, status="active", scopes=None, expires_at=None):
    prefix, secret, digest = new_key(environment)
    with factory() as db:
        row = ManagedAPIKey(
            id=f"key-{prefix[-8:]}",
            name="test key",
            environment=environment,
            key_prefix=prefix,
            secret_hash=digest,
            scopes=scopes or ["registry:read"],
            status=status,
            created_by="test",
            expires_at=expires_at,
        )
        db.add(row)
        db.commit()
    return secret


def test_sandbox_key_is_rejected_by_production_and_logged(monkeypatch):
    client, engine, factory = make_test_client(monkeypatch, "production")
    secret = insert_key(factory, "sandbox")

    response = client.get("/protected", headers={"X-API-Key": secret})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    with factory() as db:
        event = db.scalar(select(APIKeySecurityEvent).where(APIKeySecurityEvent.event_type == "environment_mismatch"))
        assert event is not None
        assert event.expected_environment == "production"
        assert event.key_environment == "sandbox"
        assert secret not in str(event.details)
    engine.dispose()


def test_managed_key_works_only_in_its_configured_environment(monkeypatch):
    client, engine, factory = make_test_client(monkeypatch, "sandbox")
    secret = insert_key(factory, "sandbox")

    response = client.get("/protected", headers={"X-API-Key": secret})

    assert response.status_code == 200
    assert response.json()["identity"].startswith("managed-api-key:")
    engine.dispose()


def test_managed_key_scope_and_revocation_are_enforced(monkeypatch):
    client, engine, factory = make_test_client(monkeypatch, "sandbox")
    read_only = insert_key(factory, "sandbox", scopes=["registry:read"])
    denied = client.post("/api/v1/ingestion/uploads", headers={"X-API-Key": read_only})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "API_KEY_SCOPE_DENIED"

    revoked = insert_key(factory, "sandbox", status="revoked", scopes=["registry:read"])
    invalid = client.get("/protected", headers={"X-API-Key": revoked})
    assert invalid.status_code == 401
    engine.dispose()


def test_expired_managed_key_is_rejected(monkeypatch):
    client, engine, factory = make_test_client(monkeypatch, "sandbox")
    expired = insert_key(
        factory,
        "sandbox",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    response = client.get("/protected", headers={"X-API-Key": expired})

    assert response.status_code == 401
    engine.dispose()


def test_managed_key_never_falls_back_to_legacy_key_list_when_disabled(monkeypatch):
    client, engine, factory = make_test_client(monkeypatch, "production")
    sandbox_secret = insert_key(factory, "sandbox")
    monkeypatch.setattr(settings, "managed_api_keys_enabled", False)
    monkeypatch.setattr(settings, "registry_api_keys", sandbox_secret)

    response = client.get("/protected", headers={"X-API-Key": sandbox_secret})

    assert response.status_code == 503
    assert "Managed API keys are disabled" in response.json()["detail"]
    engine.dispose()
