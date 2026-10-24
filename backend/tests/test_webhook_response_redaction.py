from src.developer_platform import _webhook_response_excerpt


def test_webhook_response_excerpt_contains_only_status_metadata():
    excerpt = _webhook_response_excerpt(500)

    assert excerpt == "HTTP 500; response body omitted"
    assert "password" not in excerpt.lower()
    assert "token" not in excerpt.lower()
