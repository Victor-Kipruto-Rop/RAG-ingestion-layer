from src import developer_platform


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.request = None
        self.status_code = 200
        self.__class__.last_instance = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeResponse(self.status_code)


def test_send_email_uses_resend_api_when_configured(monkeypatch):
    monkeypatch.setattr(developer_platform.settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(developer_platform.settings, "resend_from_email", "PesaGuard <no-reply@example.com>")
    monkeypatch.setattr(developer_platform.settings, "smtp_host", "")
    monkeypatch.setattr(developer_platform.httpx, "Client", FakeClient)

    developer_platform._send_email("developer@example.com", "Verify your account", "Code: 123456")

    url, request = FakeClient.last_instance.request
    assert url == "https://api.resend.com/emails"
    assert request["headers"]["Authorization"] == "Bearer re_test_secret"
    assert request["json"] == {
        "from": "PesaGuard <no-reply@example.com>",
        "to": ["developer@example.com"],
        "subject": "Verify your account",
        "text": "Code: 123456",
    }


def test_resend_delivery_failure_does_not_silently_fallback_to_smtp(monkeypatch):
    monkeypatch.setattr(developer_platform.settings, "resend_api_key", "re_test_secret")
    monkeypatch.setattr(developer_platform.settings, "resend_from_email", "PesaGuard <no-reply@example.com>")
    monkeypatch.setattr(developer_platform.settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(developer_platform.settings, "smtp_from_email", "fallback@example.com")
    monkeypatch.setattr(developer_platform.httpx, "Client", FakeClient)
    FakeClient.last_instance = None

    # The fake response below is controlled through the client class to verify
    # that a Resend API error is surfaced rather than silently switching providers.
    original_post = FakeClient.post

    def rejected_post(self, url, **kwargs):
        self.request = (url, kwargs)
        return FakeResponse(422)

    monkeypatch.setattr(FakeClient, "post", rejected_post)
    import pytest
    with pytest.raises(RuntimeError, match="Resend email delivery failed with HTTP 422"):
        developer_platform._send_email("developer@example.com", "Verify", "Code: 123456")
    assert FakeClient.last_instance.request[0] == "https://api.resend.com/emails"
    monkeypatch.setattr(FakeClient, "post", original_post)
