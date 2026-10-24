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


def test_login_rate_limit_is_scoped_to_ip_and_normalized_email(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from src import developer_platform as platform

    buckets = []
    monkeypatch.setattr(platform, "_require_platform_config", lambda: None)
    monkeypatch.setattr(platform, "_check_login_rate", lambda identity: buckets.append(identity))
    monkeypatch.setattr(platform, "verify_password", lambda password, encoded: False)

    class EmptyDB:
        def scalar(self, *_args, **_kwargs):
            return None

    payload = platform.LoginRequest(email="Developer@Example.com", password="not-a-real-password")
    request = SimpleNamespace(client=SimpleNamespace(host="203.0.113.10"))
    with pytest.raises(HTTPException) as exc:
        platform.developer_login(payload, request, object(), EmptyDB())

    assert exc.value.status_code == 401
    assert buckets == ["203.0.113.10", "developer-email:developer@example.com"]


def test_developer_session_cookie_signature_and_expiry(monkeypatch):
    import time
    from src import developer_platform as platform

    monkeypatch.setattr(settings, "session_secret", "s" * 48)
    token = platform._sign_session({
        "sub": "developer-1", "jti": "session-1", "csrf": "csrf-value",
        "iat": int(time.time()), "exp": int(time.time()) + 60,
    })
    claims = platform._decode_session(token)
    assert claims["sub"] == "developer-1"
    assert claims["jti"] == "session-1"
    assert platform._decode_session(token + "tampered") is None
    expired = platform._sign_session({
        "sub": "developer-1", "jti": "session-2", "csrf": "csrf-value",
        "iat": int(time.time()) - 120, "exp": int(time.time()) - 1,
    })
    assert platform._decode_session(expired) is None
