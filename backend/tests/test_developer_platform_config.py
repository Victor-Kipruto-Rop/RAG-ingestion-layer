from src.developer_platform import developer_platform_config


def test_developer_platform_exposes_distinct_environment_origins_and_key_prefixes():
    config = developer_platform_config()
    sandbox = config["sandbox_base_url"]
    production = config["production_base_url"]

    assert sandbox.startswith("https://")
    assert production.startswith("https://")
    assert sandbox != production
    assert config["key_prefixes"] == {
        "sandbox": "pg_sandbox_",
        "production": "pg_live_",
    }
    assert "Python" in config["sdk_languages"]
    assert "JavaScript" in config["sdk_languages"]
    assert "C#" in config["sdk_languages"]


def test_platform_config_does_not_claim_both_environments_share_a_host():
    config = developer_platform_config()
    assert config["sandbox_base_url"].split("/")[2] != config["production_base_url"].split("/")[2]


from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src import developer_platform
from src.config import settings


def test_signup_and_password_reset_fail_closed_without_session_signing(monkeypatch):
    monkeypatch.setattr(settings, "developer_access_token_secret", "d" * 40)
    monkeypatch.setattr(settings, "session_secret", "")
    monkeypatch.setattr(settings, "resend_api_key", "resend-test-key")
    monkeypatch.setattr(settings, "resend_from_email", "noreply@example.test")
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 40)

    with pytest.raises(HTTPException) as exc:
        developer_platform._require_platform_config()

    assert exc.value.status_code == 503
    assert "session signing" in exc.value.detail.lower()


def test_production_oauth_requires_an_explicit_callback_origin(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "developer_oauth_callback_base_url", "")

    with pytest.raises(HTTPException) as exc:
        developer_platform._oauth_callback_url(SimpleNamespace(base_url="https://api.example.test/"), "google")

    assert exc.value.status_code == 503
    assert "DEVELOPER_OAUTH_CALLBACK_BASE_URL" in exc.value.detail


def test_production_oauth_callback_is_built_from_explicit_https_origin(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "developer_oauth_callback_base_url", "https://api.example.test/")

    callback = developer_platform._oauth_callback_url(SimpleNamespace(base_url="http://internal/"), "github")

    assert callback == "https://api.example.test/api/v1/developer/auth/oauth/github/callback"


@pytest.mark.parametrize("origin", ["http://api.example.test", "https://user:password@api.example.test"])
def test_production_oauth_rejects_insecure_or_credentialed_callback_origins(monkeypatch, origin):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "developer_oauth_callback_base_url", origin)

    with pytest.raises(HTTPException) as exc:
        developer_platform._oauth_callback_url(SimpleNamespace(base_url="https://internal/"), "google")

    assert exc.value.status_code == 503


from src.developer_platform import _validate_webhook_url


def test_webhook_url_validation_rejects_insecure_and_private_targets():
    for target in (
        "http://example.com/hook",
        "https://localhost/hook",
        "https://127.0.0.1/hook",
        "https://192.168.1.10/hook",
        "https://user:password@example.com/hook",
    ):
        with pytest.raises(HTTPException):
            _validate_webhook_url(target)


def test_webhook_url_validation_rejects_hostnames_resolving_to_private_addresses(monkeypatch):
    import socket

    def fake_getaddrinfo(*_args, **_kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(HTTPException):
        _validate_webhook_url("https://public-looking.example/hook")


def test_webhook_url_validation_accepts_public_https_target(monkeypatch):
    import socket

    def fake_getaddrinfo(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    assert _validate_webhook_url("https://hooks.example.test/receive") is None


def test_production_oauth_start_requires_frontend_redirect_origin(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "developer_access_token_secret", "d" * 40)
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    monkeypatch.setattr(settings, "developer_frontend_url", "")
    monkeypatch.setattr(settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "google-secret")

    with pytest.raises(HTTPException) as exc:
        developer_platform.developer_oauth_start("google", SimpleNamespace(base_url="https://api.example.test/"))

    assert exc.value.status_code == 503
    assert "DEVELOPER_FRONTEND_URL" in exc.value.detail


def test_developer_login_is_not_blocked_by_email_transport_configuration(monkeypatch):
    from types import SimpleNamespace
    from fastapi import Response
    from src.developer_platform import LoginRequest, developer_login

    monkeypatch.setattr(settings, "developer_access_token_secret", "d" * 40)
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_otp_pepper", "")
    monkeypatch.setattr(settings, "resend_api_key", "")
    monkeypatch.setattr(settings, "resend_from_email", "")
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "smtp_from_email", "")
    monkeypatch.setattr(developer_platform, "_check_login_rate", lambda _host: None)
    monkeypatch.setattr(developer_platform, "_check_account_rate", lambda _email: None)

    class EmptyDatabase:
        def scalar(self, *_args, **_kwargs):
            return None

    with pytest.raises(HTTPException) as exc:
        developer_login(
            LoginRequest(email="developer@example.com", password="not-the-password"),
            SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
            Response(),
            EmptyDatabase(),
        )

    # The request reaches credential verification (401), rather than failing early
    # with 503 just because email OTP delivery is unavailable.
    assert exc.value.status_code == 401
    assert "invalid email or password" in exc.value.detail.lower()


def test_developer_signup_does_not_claim_otp_sent_when_email_delivery_fails(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from src.developer_platform import SignupRequest, signup_request_otp

    monkeypatch.setattr(settings, "developer_access_token_secret", "d" * 40)
    monkeypatch.setattr(settings, "session_secret", "s" * 40)
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 40)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-key")
    monkeypatch.setattr(settings, "resend_from_email", "noreply@example.test")
    monkeypatch.setattr(developer_platform, "_check_login_rate", lambda _host: None)
    monkeypatch.setattr(developer_platform, "_check_account_rate", lambda _email: None)
    monkeypatch.setattr(developer_platform, "_send_email", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mail unavailable")))

    class EmptyDatabase:
        def __init__(self):
            self.rows = []

        def scalar(self, *_args, **_kwargs):
            return None

        def scalars(self, *_args, **_kwargs):
            return SimpleNamespace(all=lambda: [])

        def add(self, row):
            self.rows.append(row)

        def commit(self):
            return None

    with pytest.raises(HTTPException) as exc:
        signup_request_otp(
            SignupRequest(email="developer@example.com", display_name="Test Developer",
                          workspace_name="Test Workspace", password="A-long-unique-password-42"),
            SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")),
            EmptyDatabase(),
        )

    assert exc.value.status_code == 503
    assert "verification email could not be sent" in exc.value.detail.lower()
