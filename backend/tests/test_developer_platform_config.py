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
