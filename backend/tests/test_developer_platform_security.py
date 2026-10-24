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
