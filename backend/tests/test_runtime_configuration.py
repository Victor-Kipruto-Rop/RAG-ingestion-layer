import pytest

from src.config import settings, validate_runtime_config


def test_development_does_not_require_production_secrets(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "api_environment", "sandbox")
    monkeypatch.setattr(settings, "registry_api_keys", "")
    monkeypatch.setattr(settings, "database_url", "sqlite:///./local.db")
    monkeypatch.setattr(settings, "r2_account_id", "")
    monkeypatch.setattr(settings, "r2_access_key_id", "")
    monkeypatch.setattr(settings, "r2_secret_access_key", "")
    monkeypatch.setattr(settings, "r2_bucket_name", "")
    validate_runtime_config()


def test_production_must_explicitly_use_production_api_environment(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_environment", "sandbox")
    monkeypatch.setattr(settings, "registry_api_keys", "unit-test-key")
    monkeypatch.setattr(settings, "database_url", "postgresql://example.invalid/test")
    monkeypatch.setattr(settings, "r2_account_id", "account")
    monkeypatch.setattr(settings, "r2_access_key_id", "access")
    monkeypatch.setattr(settings, "r2_secret_access_key", "secret")
    monkeypatch.setattr(settings, "r2_bucket_name", "bucket")
    with pytest.raises(RuntimeError, match="API_ENVIRONMENT=production"):
        validate_runtime_config()


def test_production_rejects_invalid_api_environment(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "api_environment", "preview")
    monkeypatch.setattr(settings, "registry_api_keys", "unit-test-key")
    monkeypatch.setattr(settings, "database_url", "postgresql://example.invalid/test")
    monkeypatch.setattr(settings, "r2_account_id", "account")
    monkeypatch.setattr(settings, "r2_access_key_id", "access")
    monkeypatch.setattr(settings, "r2_secret_access_key", "secret")
    monkeypatch.setattr(settings, "r2_bucket_name", "bucket")
    with pytest.raises(RuntimeError, match="API_ENVIRONMENT must be sandbox or production"):
        validate_runtime_config()
