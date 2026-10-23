import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src import api_keys, security
from src.database import Base, get_db
from src.models import ApiKey, ApiKeyAuditEvent

JWT_SECRET = "unit-test-only-jwt-secret"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def issue_token(org_id="org-a", user_id="user-a", roles=None, verified=True):
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = {
        "sub": user_id,
        "org_id": org_id,
        "roles": roles if roles is not None else ["owner"],
        "organization_verified": verified,
        "iss": "https://identity.test",
        "aud": "pesaguard-datasource",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signed = f"{header}.{payload}"
    signature = _b64(hmac.new(JWT_SECRET.encode(), signed.encode(), hashlib.sha256).digest())
    return f"{signed}.{signature}"


@pytest.fixture
def api_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(api_keys.router)

    @app.get("/api/v1/registry/lookup", dependencies=[Depends(security.require_api_key)])
    def protected_lookup():
        return {"ok": True}

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(api_keys.settings, "api_key_auth_jwt_secret", JWT_SECRET)
    monkeypatch.setattr(api_keys.settings, "api_key_auth_jwt_issuer", "https://identity.test")
    monkeypatch.setattr(api_keys.settings, "api_key_auth_jwt_audience", "pesaguard-datasource")
    monkeypatch.setattr(api_keys.settings, "app_env", "development")
    monkeypatch.setattr(security.settings, "api_environment", "sandbox")
    monkeypatch.setattr(security.settings, "registry_api_keys", "")
    monkeypatch.setattr(security.settings, "require_hmac", False)
    monkeypatch.setattr(security.settings, "redis_url", "")
    monkeypatch.setattr(security, "SessionLocal", TestSession)
    client = TestClient(app)
    try:
        yield client, TestSession
    finally:
        engine.dispose()


def create_key(client, token, environment="sandbox", scopes=None):
    return client.post(
        "/api/v1/keys",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Automated test key",
            "environment": environment,
            "expires_in_days": 30,
            "scopes": scopes or ["registry:read"],
        },
    )


def test_key_secret_is_hash_only_and_list_is_organization_scoped(api_client):
    client, Session = api_client
    token_a = issue_token(org_id="org-a", user_id="user-a")
    token_b = issue_token(org_id="org-b", user_id="user-b")
    created_a = create_key(client, token_a)
    created_b = create_key(client, token_b)
    assert created_a.status_code == 201
    assert created_b.status_code == 201
    secret = created_a.json()["secret"]

    with Session() as db:
        stored = db.scalar(select(ApiKey).where(ApiKey.id == created_a.json()["id"]))
        assert stored.secret_hash == hashlib.sha256(secret.encode()).hexdigest()
        assert stored.secret_hash != secret

    listed = client.get("/api/v1/keys", headers={"Authorization": f"Bearer {token_a}"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [created_a.json()["id"]]
    assert all("secret" not in item for item in listed.json()["items"])

    cross_org_revoke = client.delete(
        f"/api/v1/keys/{created_b.json()['id']}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert cross_org_revoke.status_code == 404


def test_production_key_requires_verified_organization_and_owner_or_admin(api_client):
    client, _ = api_client
    unverified = create_key(client, issue_token(verified=False), environment="production")
    assert unverified.status_code == 403

    non_admin = create_key(
        client, issue_token(roles=["developer"], verified=True), environment="production"
    )
    assert non_admin.status_code == 403

    approved = create_key(client, issue_token(verified=True), environment="production")
    assert approved.status_code == 201
    assert approved.json()["environment"] == "production"
    assert approved.json()["secret"].startswith("pg_live_")


def test_sandbox_key_used_on_production_is_rejected_and_audited(api_client, monkeypatch):
    client, Session = api_client
    created = create_key(client, issue_token(), environment="sandbox")
    assert created.status_code == 201
    secret = created.json()["secret"]
    monkeypatch.setattr(security.settings, "api_environment", "production")

    response = client.get("/api/v1/registry/lookup", headers={"X-API-Key": secret})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_ENVIRONMENT_MISMATCH"

    with Session() as db:
        event = db.scalar(select(ApiKeyAuditEvent).where(
            ApiKeyAuditEvent.action == "api_key.environment_mismatch"
        ))
        assert event is not None
        assert event.details["key_environment"] == "sandbox"
        assert secret not in json.dumps(event.details)


def test_scope_denial_is_explicit(api_client):
    client, _ = api_client
    created = create_key(client, issue_token(), scopes=["sources:read"])
    assert created.status_code == 201
    response = client.get("/api/v1/registry/lookup", headers={"X-API-Key": created.json()["secret"]})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_SCOPE_INSUFFICIENT"
