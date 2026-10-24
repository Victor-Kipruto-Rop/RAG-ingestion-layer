from fastapi.testclient import TestClient

from src.config import settings
from src.main import app


def test_social_providers_are_disabled_without_provider_credentials(monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_client_id", "")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "")
    monkeypatch.setattr(settings, "github_oauth_client_id", "")
    monkeypatch.setattr(settings, "github_oauth_client_secret", "")
    monkeypatch.setattr(settings, "admin_oauth_allowed_emails", "")

    response = TestClient(app).get("/api/v1/admin/oauth/providers")

    assert response.status_code == 200
    assert response.json() == {"google": False, "github": False}


def test_google_oauth_start_requires_explicit_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "client-secret")
    monkeypatch.setattr(settings, "admin_oauth_allowed_emails", "")

    response = TestClient(app).get("/api/v1/admin/oauth/google/start")

    assert response.status_code == 503
    assert "allowlisted operator" in response.json()["detail"]


def test_oauth_callback_rejects_missing_or_mismatched_state():
    response = TestClient(app).get(
        "/api/v1/admin/oauth/google/callback?code=untrusted-code&state=wrong-state",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "state validation failed" in response.json()["detail"]


def test_oauth_provider_configuration_requires_client_id_and_secret(monkeypatch):
    monkeypatch.setattr(settings, "google_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "")
    monkeypatch.setattr(settings, "admin_oauth_allowed_emails", "operator@example.com")

    response = TestClient(app).get("/api/v1/admin/oauth/providers")

    assert response.status_code == 200
    assert response.json()["google"] is False
