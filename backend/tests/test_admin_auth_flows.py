import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src import admin_auth
from src.config import settings
from src.models import AdminAccount, AdminAuthChallenge, AdminSession


def test_password_hash_verifies_and_does_not_store_plaintext():
    password = "correct horse battery staple 2026!"
    encoded = admin_auth.hash_password(password, iterations=1000)
    assert encoded != password
    assert admin_auth.verify_password(password, encoded)
    assert not admin_auth.verify_password("wrong password", encoded)


def test_otp_digest_is_bound_to_email_purpose_and_code(monkeypatch):
    monkeypatch.setattr(settings, "auth_otp_pepper", "test-pepper-not-for-production")
    base = admin_auth._otp_digest("operator@example.com", "signup", "123456")
    assert base == admin_auth._otp_digest("operator@example.com", "signup", "123456")
    assert base != admin_auth._otp_digest("other@example.com", "signup", "123456")
    assert base != admin_auth._otp_digest("operator@example.com", "password_reset", "123456")
    assert base != admin_auth._otp_digest("operator@example.com", "signup", "654321")


def test_signup_request_enforces_minimum_password_length():
    with pytest.raises(ValidationError):
        admin_auth.SignupRequest(email="operator@example.com", display_name="Operator", password="short")


def test_otp_must_be_exactly_six_digits():
    with pytest.raises(ValidationError):
        admin_auth.OtpVerifyRequest(email="operator@example.com", code="12AB56")
    with pytest.raises(ValidationError):
        admin_auth.OtpVerifyRequest(email="operator@example.com", code="12345")


def test_email_normalization_and_validation():
    assert admin_auth._normalize_email("  Operator@Example.COM ") == "operator@example.com"
    with pytest.raises(HTTPException) as error:
        admin_auth._normalize_email("not-an-email")
    assert error.value.status_code == 422


def test_signed_sessions_have_unique_ids_and_refresh_preserves_id(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "unit-test-session-secret-with-enough-entropy")
    token, claims = admin_auth.issue_session_token(email="operator@example.com", auth_method="password")
    decoded = admin_auth.decode_session_token(token)
    assert decoded["jti"] == claims["jti"]
    assert decoded["email"] == "operator@example.com"
    refreshed, renewed = admin_auth.refresh_session_token(claims)
    assert admin_auth.decode_session_token(refreshed)["jti"] == claims["jti"]
    assert renewed["csrf"] == claims["csrf"]


def test_auth_tables_are_registered_for_the_migration():
    assert AdminAccount.__tablename__ == "admin_accounts"
    assert AdminAuthChallenge.__tablename__ == "admin_auth_challenges"
    assert AdminSession.__tablename__ == "admin_sessions"
