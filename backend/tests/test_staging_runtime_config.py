import pytest

from src.config import settings, validate_runtime_config


def _configure_valid_staging(monkeypatch):
    values = {
        "app_env": "staging",
        "database_url": "postgresql+psycopg://registry:unused@localhost:5432/registry",
        "registry_api_keys": "ci-registry-key-not-used-for-network",
        "r2_account_id": "staging-account",
        "r2_access_key_id": "staging-access-key",
        "r2_secret_access_key": "staging-secret-key",
        "r2_bucket_name": "registry-staging",
        "require_hmac": False,
        "redis_url": "redis://localhost:6379/0",
        "api_key_auth_jwt_secret": "",
        "api_key_auth_jwt_keys_json": "",
        "api_key_auth_jwt_issuer": "",
        "api_key_auth_jwt_audience": "",
        "developer_access_token_secret": "d" * 48,
        "developer_webhook_encryption_key": "w" * 48,
        "api_environment": "sandbox",
        "session_cookie_secure": True,
        "admin_password_hash": "",
        "cors_origins": "https://staging.pesaguard.co.ke",
        "developer_public_base_url": "https://sandbox-api.pesaguard.co.ke",
        "developer_production_base_url": "https://api.pesaguard.co.ke",
        "admin_signup_allowed_emails": "",
        "auth_otp_pepper": "",
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)


def test_staging_uses_production_grade_runtime_validation(monkeypatch):
    _configure_valid_staging(monkeypatch)

    validate_runtime_config()


def test_staging_rejects_sqlite_database(monkeypatch):
    _configure_valid_staging(monkeypatch)
    monkeypatch.setattr(settings, "database_url", "sqlite:///./registry.db")

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        validate_runtime_config()


def test_staging_requires_redis_and_identity_signing(monkeypatch):
    _configure_valid_staging(monkeypatch)
    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.setattr(settings, "developer_access_token_secret", "")
    monkeypatch.setattr(settings, "developer_webhook_encryption_key", "")

    with pytest.raises(RuntimeError) as error:
        validate_runtime_config()

    message = str(error.value)
    assert "REDIS_URL" in message
    assert "PesaGuard identity signing keys or DEVELOPER_ACCESS_TOKEN_SECRET" in message


def test_staging_requires_distinct_https_sandbox_and_production_hosts(monkeypatch):
    _configure_valid_staging(monkeypatch)
    monkeypatch.setattr(settings, "developer_production_base_url", "https://sandbox-api.pesaguard.co.ke")

    with pytest.raises(RuntimeError, match="different hostnames"):
        validate_runtime_config()
