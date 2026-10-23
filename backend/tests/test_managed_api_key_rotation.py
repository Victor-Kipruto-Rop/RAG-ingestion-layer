import uuid

from fastapi.testclient import TestClient
from src.config import settings
from src.database import Base, SessionLocal, engine
from src.main import app
from src.models import ManagedAPIKey

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def headers(token="test-operator-token"):
    return {"Authorization": f"Bearer {token}"}


def test_rotation_revokes_old_key_and_returns_new_secret_once(monkeypatch):
    monkeypatch.setattr(settings, "datasource_admin_token", "test-operator-token")
    monkeypatch.setattr(settings, "datasource_environment", "sandbox")
    created = client.post(
        "/api/v1/admin/api-keys",
        headers=headers(),
        json={"name": f"rotate-{uuid.uuid4().hex[:8]}", "environment": "sandbox", "scopes": ["registry:read"]},
    )
    assert created.status_code == 201, created.text
    old_item = created.json()["item"]
    old_secret = created.json()["secret"]

    rotated = client.post(
        f"/api/v1/admin/api-keys/{old_item['id']}/rotate",
        headers=headers(),
        json={"expires_in_days": 90},
    )
    assert rotated.status_code == 201, rotated.text
    payload = rotated.json()
    new_item = payload["item"]
    new_secret = payload["secret"]
    assert new_item["id"] != old_item["id"]
    assert new_item["environment"] == old_item["environment"] == "sandbox"
    assert new_secret.startswith("pg_sandbox_")
    assert new_secret != old_secret
    assert "cannot be retrieved again" in payload["warning"].lower()

    old_request = client.get("/api/v1/registry/search", params={"q": "example"}, headers={"X-API-Key": old_secret})
    new_request = client.get("/api/v1/registry/search", params={"q": "example"}, headers={"X-API-Key": new_secret})
    assert old_request.status_code == 401
    assert new_request.status_code == 200

    with SessionLocal() as db:
        old = db.get(ManagedAPIKey, old_item["id"])
        new = db.get(ManagedAPIKey, new_item["id"])
        assert old is not None and old.status == "revoked"
        assert new is not None and new.status == "active"
        db.delete(old)
        db.delete(new)
        db.commit()
