import pytest
from fastapi import HTTPException

from src.developer_platform import _otp_digest, _validate_webhook_url
from src.config import settings


def test_webhook_endpoint_requires_https():
    with pytest.raises(HTTPException) as exc:
        _validate_webhook_url("http://example.com/hook")
    assert exc.value.status_code == 422


@pytest.mark.parametrize("url", [
    "https://localhost/hook",
    "https://127.0.0.1/hook",
    "https://[::1]/hook",
    "https://user:password@example.com/hook",
    "https://service.internal/hook",
])
def test_webhook_endpoint_rejects_local_or_credentialed_targets(url):
    with pytest.raises(HTTPException) as exc:
        _validate_webhook_url(url)
    assert exc.value.status_code == 422


def test_otp_digest_is_bound_to_email_and_purpose(monkeypatch):
    monkeypatch.setattr(settings, "auth_otp_pepper", "p" * 40)
    signup = _otp_digest("developer@example.com", "signup", "123456")
    reset = _otp_digest("developer@example.com", "password_reset", "123456")
    other_email = _otp_digest("other@example.com", "signup", "123456")
    assert signup != reset
    assert signup != other_email


def test_account_rate_limit_uses_stable_non_reversible_identifier(monkeypatch):
    from src import developer_platform

    calls = []
    monkeypatch.setattr(developer_platform, "_check_login_rate", calls.append)

    developer_platform._check_account_rate("Person@example.com")
    developer_platform._check_account_rate("person@example.com")
    developer_platform._check_account_rate("another@example.com")

    assert calls[0] == calls[1]
    assert calls[0] != calls[2]
    assert calls[0].startswith("developer-account:")
    assert "person@example.com" not in calls[0]


def test_account_rate_limit_does_not_pass_raw_email_to_shared_limiter(monkeypatch):
    from src import developer_platform

    observed = []
    monkeypatch.setattr(developer_platform, "_check_login_rate", observed.append)

    developer_platform._check_account_rate("Sensitive.User@example.com")

    assert len(observed) == 1
    assert "Sensitive.User@example.com" not in observed[0]
    assert "sensitive.user@example.com" not in observed[0]
