import pytest
from fastapi import HTTPException

from src import admin_auth
from src.config import settings


def test_auth_config_requires_session_signing_email_delivery_and_signup_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "s" * 32)
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 32)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-key")
    monkeypatch.setattr(settings, "resend_from_email", "auth@example.com")
    monkeypatch.setattr(settings, "admin_signup_allowed_emails", "operator@example.com")

    result = admin_auth.auth_config()

    assert result["signup_enabled"] is True
    assert result["password_reset_enabled"] is True
    assert result["password_min_length"] == 12


def test_auth_config_disables_flows_when_session_signing_is_weak(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "short")
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 32)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-key")
    monkeypatch.setattr(settings, "resend_from_email", "auth@example.com")
    monkeypatch.setattr(settings, "admin_signup_allowed_emails", "operator@example.com")

    result = admin_auth.auth_config()

    assert result["signup_enabled"] is False
    assert result["password_reset_enabled"] is False


def test_signup_reports_email_delivery_failure_for_allowlisted_account(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "s" * 32)
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 32)
    monkeypatch.setattr(settings, "resend_api_key", "test-resend-key")
    monkeypatch.setattr(settings, "resend_from_email", "auth@example.com")
    monkeypatch.setattr(settings, "admin_signup_allowed_emails", "operator@example.com")
    monkeypatch.setattr(admin_auth, "_check_login_rate", lambda _host: None)

    class EmptyDatabase:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def scalar(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(admin_auth, "SessionLocal", EmptyDatabase)
    monkeypatch.setattr(
        admin_auth,
        "_create_auth_challenge",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            HTTPException(503, "Verification email could not be sent.")
        ),
    )
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    payload = admin_auth.SignupRequest(
        email="operator@example.com",
        display_name="Test Operator",
        password="a-long-test-password",
    )

    with pytest.raises(HTTPException) as error:
        admin_auth.signup_request_otp(payload, request)

    assert error.value.status_code == 503
    assert "email could not be sent" in error.value.detail.lower()
