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


def test_oauth_callback_redirects_to_internal_dashboard(monkeypatch):
    import src.admin_auth as auth

    monkeypatch.setattr(settings, "admin_oauth_allowed_emails", "operator@example.com")
    monkeypatch.setattr(settings, "admin_frontend_url", "https://datasource.example.com")

    async def verified_identity(provider, code, callback):
        assert provider == "google"
        assert code == "trusted-test-code"
        return "operator@example.com"

    monkeypatch.setattr(auth, "_oauth_identity", verified_identity)
    monkeypatch.setattr(auth, "_issue_admin_oauth_session", lambda response, email, provider: None)

    response = TestClient(app).get(
        "/api/v1/admin/oauth/google/callback?code=trusted-test-code&state=state-123",
        cookies={"pg_oauth_state_google": "state-123"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "https://datasource.example.com/internal"


def test_oauth_callback_uses_shared_frontend_fallback(monkeypatch):
    import src.admin_auth as auth

    monkeypatch.setattr(settings, "admin_oauth_allowed_emails", "operator@example.com")
    monkeypatch.setattr(settings, "admin_frontend_url", "")
    monkeypatch.setattr(settings, "developer_frontend_url", "https://datasource.example.com/")

    async def verified_identity(provider, code, callback):
        return "operator@example.com"

    monkeypatch.setattr(auth, "_oauth_identity", verified_identity)
    monkeypatch.setattr(auth, "_issue_admin_oauth_session", lambda response, email, provider: None)

    response = TestClient(app).get(
        "/api/v1/admin/oauth/google/callback?code=test-code&state=state-456",
        cookies={"pg_oauth_state_google": "state-456"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "https://datasource.example.com/internal"
