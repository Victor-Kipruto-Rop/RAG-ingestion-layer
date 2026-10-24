import pytest

from src.config import settings, validate_runtime_config


@pytest.fixture
def safe_development_config(monkeypatch):
    values = {
        "app_env": "development",
        "cors_origins": "http://localhost:5173",
        "admin_password_hash": "",
        "session_secret": "",
        "worker_poll_seconds": 2.0,
        "worker_max_attempts": 3,
        "worker_retry_seconds": 30,
        "worker_retry_max_seconds": 900,
        "worker_stale_after_seconds": 900,
        "worker_max_jobs_per_run": 10,
        "ingestion_batch_size": 5000,
        "max_upload_bytes": 52428800,
        "max_direct_upload_bytes": 5368709120,
        "direct_upload_url_ttl_seconds": 3600,
        "hmac_clock_skew_seconds": 300,
        "hmac_nonce_ttl_seconds": 600,
        "registry_rate_limit_capacity": 60,
        "registry_rate_limit_refill_per_second": 1.0,
        "registry_cache_ttl_seconds": 300,
        "registry_cache_negative_ttl_seconds": 30,
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value)
    return values


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("worker_poll_seconds", 0, "WORKER_POLL_SECONDS"),
        ("worker_max_attempts", 0, "WORKER_MAX_ATTEMPTS"),
        ("worker_retry_seconds", 0, "WORKER_RETRY_SECONDS"),
        ("worker_retry_max_seconds", 29, "WORKER_RETRY_MAX_SECONDS"),
        ("worker_stale_after_seconds", 0, "WORKER_STALE_AFTER_SECONDS"),
        ("worker_max_jobs_per_run", 0, "WORKER_MAX_JOBS_PER_RUN"),
        ("ingestion_batch_size", 0, "INGESTION_BATCH_SIZE"),
        ("max_upload_bytes", 0, "upload size limits"),
        ("max_direct_upload_bytes", 0, "upload size limits"),
        ("direct_upload_url_ttl_seconds", 0, "DIRECT_UPLOAD_URL_TTL_SECONDS"),
        ("hmac_clock_skew_seconds", -1, "HMAC clock skew"),
        ("hmac_nonce_ttl_seconds", 0, "HMAC clock skew"),
        ("registry_rate_limit_capacity", 0, "registry rate-limit capacity"),
        ("registry_rate_limit_refill_per_second", 0, "registry rate-limit capacity"),
        ("registry_cache_ttl_seconds", -1, "registry cache TTL"),
        ("registry_cache_negative_ttl_seconds", -1, "registry cache TTL"),
    ],
)
def test_runtime_config_rejects_unsafe_limits(safe_development_config, monkeypatch, name, value, message):
    monkeypatch.setattr(settings, name, value)
    with pytest.raises(RuntimeError, match=message):
        validate_runtime_config()


def test_runtime_config_accepts_safe_limits(safe_development_config):
    validate_runtime_config()
