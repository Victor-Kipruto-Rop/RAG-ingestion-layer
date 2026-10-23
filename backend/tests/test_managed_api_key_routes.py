import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import APIKeySecurityEvent, ManagedAPIKey

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def admin_headers(token="test-operator-token"):
    return {"Authorization": f"Bearer {token}"}


def test_key_management_requires_operator_token(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    assert client.get("/api/v1/admin/api-keys").status_code == 401
    assert client.get("/api/v1/admin/api-keys", headers=admin_headers("wrong")).status_code == 401
    assert client.get("/api/v1/admin/api-keys", headers=admin_headers()).status_code == 200


def test_create_key_shows_secret_once_and_stores_only_hash(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    label = f"test-key-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": label, "environment": "sandbox", "scopes": ["registry:read"], "expires_in_days": 30},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    secret = payload["secret"]
    key_id = payload["item"]["id"]
    assert secret.startswith("pg_sandbox_")
    assert payload["item"]["key_prefix"] in secret
    assert "secret" not in payload["item"]

    with SessionLocal() as db:
        stored = db.get(ManagedAPIKey, key_id)
        assert stored is not None
        assert stored.secret_hash != secret
        assert len(stored.secret_hash) == 64
        assert stored.secret_hash != ""

    listing = client.get("/api/v1/admin/api-keys", headers=admin_headers()).json()
    listed = next(item for item in listing["items"] if item["id"] == key_id)
    assert "secret" not in listed
    assert secret not in str(listing)

    with SessionLocal() as db:
        row = db.get(ManagedAPIKey, key_id)
        if row:
            db.delete(row)
            db.commit()


def test_sandbox_key_is_rejected_in_production_and_event_is_recorded(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    label = f"mismatch-{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": label, "environment": "sandbox", "scopes": ["registry:read"], "expires_in_days": 30},
    )
    assert created.status_code == 201, created.text
    item = created.json()["item"]
    secret = created.json()["secret"]

    monkeypatch.setattr(settings, "datasource_environment", "production")
    response = client.get("/api/v1/registry/search", params={"q": "example"}, headers={"X-API-Key": secret})
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert "sandbox" in detail["message"].lower()
    assert "production" in detail["message"].lower()

    with SessionLocal() as db:
        event = db.scalar(
            select(APIKeySecurityEvent).where(
                APIKeySecurityEvent.key_prefix == item["key_prefix"],
                APIKeySecurityEvent.event_type == "environment_mismatch",
            ).order_by(APIKeySecurityEvent.created_at.desc())
        )
        assert event is not None
        assert event.expected_environment == "production"
        assert event.key_environment == "sandbox"
        row = db.get(ManagedAPIKey, item["id"])
        if row:
            db.delete(row)
        db.commit()


def test_scope_denial_does_not_allow_read_only_key_to_upload(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": f"read-only-{uuid.uuid4().hex[:8]}", "environment": "sandbox", "scopes": ["registry:read"]},
    )
    assert created.status_code == 201, created.text
    item = created.json()["item"]
    secret = created.json()["secret"]

    response = client.post(
        "/api/v1/ingestion/uploads",
        headers={"X-API-Key": secret},
        files={"file": ("tiny.csv", b"Company Name,Registration No\nExample Ltd,ABC-123\n", "text/csv")},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_SCOPE_DENIED"

    with SessionLocal() as db:
        row = db.get(ManagedAPIKey, item["id"])
        if row:
            db.delete(row)
        db.commit()


def test_revoked_key_cannot_authenticate(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": f"revoke-{uuid.uuid4().hex[:8]}", "environment": "sandbox", "scopes": ["registry:read"]},
    )
    assert created.status_code == 201, created.text
    item = created.json()["item"]
    secret = created.json()["secret"]
    revoked = client.delete(f"/api/v1/admin/api-keys/{item['id']}", headers=admin_headers())
    assert revoked.status_code == 200
    response = client.get("/api/v1/registry/search", params={"q": "example"}, headers={"X-API-Key": secret})
    assert response.status_code == 401

    with SessionLocal() as db:
        row = db.get(ManagedAPIKey, item["id"])
        if row:
            db.delete(row)
        db.commit()


def test_expired_managed_key_cannot_authenticate(monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": f"expired-{uuid.uuid4().hex[:8]}", "environment": "sandbox", "scopes": ["registry:read"]},
    )
    assert created.status_code == 201, created.text
    item = created.json()["item"]
    secret = created.json()["secret"]

    with SessionLocal() as db:
        row = db.get(ManagedAPIKey, item["id"])
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    response = client.get("/api/v1/registry/search", params={"q": "example"}, headers={"X-API-Key": secret})
    assert response.status_code == 401

    with SessionLocal() as db:
        row = db.get(ManagedAPIKey, item["id"])
        if row:
            db.delete(row)
        db.commit()


def test_production_key_is_rejected_in_sandbox(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "production")
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": f"reverse-mismatch-{uuid.uuid4().hex[:8]}", "environment": "production", "scopes": ["registry:read"]},
    )
    assert created.status_code == 201, created.text
    item = created.json()["item"]
    secret = created.json()["secret"]

    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    response = client.get("/api/v1/registry/search", params={"q": "example"}, headers={"X-API-Key": secret})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert "production" in response.json()["detail"]["message"].lower()

    with SessionLocal() as db:
        row = db.get(ManagedAPIKey, item["id"])
        if row:
            db.delete(row)
        db.commit()


def test_wrong_environment_prefix_is_rejected_even_when_key_is_not_in_this_database(monkeypatch):
    """Sandbox and production use separate databases, so mismatch must be detected from prefix."""
    monkeypatch.setattr(settings, "datasource_environment", "production")
    fabricated_but_well_formed_sandbox_key = "pg_sandbox_deadbeef_absolutely-not-a-valid-secret"
    response = client.get(
        "/api/v1/registry/search",
        params={"q": "example"},
        headers={"X-API-Key": fabricated_but_well_formed_sandbox_key},
    )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "API_KEY_ENVIRONMENT_MISMATCH"
    assert detail["key_environment"] == "sandbox"
    assert detail["request_environment"] == "production"

    with SessionLocal() as db:
        event = db.scalar(
            select(APIKeySecurityEvent)
            .where(
                APIKeySecurityEvent.key_prefix == "pg_sandbox_deadbeef",
                APIKeySecurityEvent.event_type == "environment_mismatch",
            )
            .order_by(APIKeySecurityEvent.created_at.desc())
        )
        assert event is not None
        assert event.key_id is None
        assert event.expected_environment == "production"
        assert event.key_environment == "sandbox"


def test_create_key_rejects_whitespace_only_name(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    response = client.post(
        "/api/v1/admin/api-keys",
        headers=admin_headers(),
        json={"name": "   ", "environment": "sandbox", "scopes": ["registry:read"]},
    )
    assert response.status_code == 422
    assert "non-whitespace" in response.json()["detail"]
