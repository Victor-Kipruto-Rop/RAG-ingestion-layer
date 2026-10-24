import pytest
from fastapi import HTTPException

from src.developer_platform import _validate_webhook_url, _webhook_response_excerpt


def test_webhook_response_excerpt_contains_only_status_metadata():
    excerpt = _webhook_response_excerpt(500)

    assert excerpt == "HTTP 500; response body omitted"
    assert "password" not in excerpt.lower()
    assert "token" not in excerpt.lower()


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/webhook",
        "https://user:password@example.com/webhook",
        "https://localhost/webhook",
        "https://127.0.0.1/webhook",
        "https://192.168.1.10/webhook",
        "https://[::1]/webhook",
    ],
)
def test_webhook_url_validation_rejects_non_public_targets(url):
    with pytest.raises(HTTPException):
        _validate_webhook_url(url)
