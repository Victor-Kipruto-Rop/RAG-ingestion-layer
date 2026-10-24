import time

from fastapi.testclient import TestClient

from src import admin_auth
from src.config import settings
from src.database import Base, engine
from src.main import app

Base.metadata.create_all(engine)


def test_workspace_overview_endpoints_require_operator_session(monkeypatch):
    monkeypatch.setattr(settings, "admin_password_hash", admin_auth.hash_password("workspace-test-password", iterations=1000))
    monkeypatch.setattr(settings, "session_secret", "s" * 48)
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "app_env", "test")
    admin_auth._attempts.clear()
    with TestClient(app) as client:
        assert client.get("/api/v1/admin/workspace/metrics").status_code == 401
        login = client.post("/api/v1/admin/login", json={"password": "workspace-test-password"})
        assert login.status_code == 200
        assert client.get("/api/v1/admin/workspace/metrics").status_code == 200
        metrics = client.get("/api/v1/admin/workspace/metrics").json()
        assert {"indexed_organizations", "ingestion_jobs", "completed_jobs", "failed_jobs", "connected_sources_count"} <= set(metrics)
        activity = client.get("/api/v1/admin/ingestion/activity").json()
        assert isinstance(activity.get("items"), list)
        quality = client.get("/api/v1/admin/registry/overview").json()
        assert "completeness_percentage" in quality
        assert quality["source"] == "database"


def test_sliding_session_renews_cookie_and_preserves_csrf(monkeypatch):
    monkeypatch.setattr(settings, "admin_password_hash", admin_auth.hash_password("workspace-test-password", iterations=1000))
    monkeypatch.setattr(settings, "session_secret", "s" * 48)
    monkeypatch.setattr(settings, "session_cookie_secure", False)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "app_env", "test")
    with TestClient(app) as client:
        login = client.post("/api/v1/admin/login", json={"password": "workspace-test-password"})
        csrf = login.json()["csrf_token"]
        before = admin_auth.decode_session_token(client.cookies.get(admin_auth.COOKIE_NAME))
        time.sleep(1)
        response = client.get("/api/v1/admin/workspace/metrics")
        after = admin_auth.decode_session_token(client.cookies.get(admin_auth.COOKIE_NAME))
        assert response.status_code == 200
        assert after["csrf"] == csrf
        assert after["exp"] >= before["exp"]
