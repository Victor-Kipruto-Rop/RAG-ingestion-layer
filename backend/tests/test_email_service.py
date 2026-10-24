from types import SimpleNamespace

import pytest

from src import email_service


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code


class FakeClient:
    calls = []
    response_status = 200

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, *, headers, json):
        self.__class__.calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse(self.__class__.response_status)


def test_resend_transport_passes_idempotency_without_logging_body(monkeypatch):
    FakeClient.calls = []
    FakeClient.response_status = 200
    monkeypatch.setattr(email_service.settings, "resend_api_key", "test-provider-secret")
    monkeypatch.setattr(email_service.settings, "resend_from_email", "no-reply@example.test")
    monkeypatch.setattr(email_service.httpx, "Client", FakeClient)

    email_service.send_transactional_email(
        "developer@example.test", "Key created", "Only the key prefix is included.",
        template_id="api_key.created", idempotency_key="api-key-created:event-1",
    )

    assert len(FakeClient.calls) == 1
    call = FakeClient.calls[0]
    assert call["headers"]["Idempotency-Key"] == "api-key-created:event-1"
    assert call["json"]["tags"] == [{"name": "template", "value": "api_key.created"}]
    assert "test-provider-secret" not in repr(call["json"])


def test_resend_provider_rejection_raises_safe_error(monkeypatch):
    FakeClient.calls = []
    FakeClient.response_status = 429
    monkeypatch.setattr(email_service.settings, "resend_api_key", "test-provider-secret")
    monkeypatch.setattr(email_service.settings, "resend_from_email", "no-reply@example.test")
    monkeypatch.setattr(email_service.httpx, "Client", FakeClient)

    with pytest.raises(RuntimeError, match="HTTP 429"):
        email_service.send_transactional_email(
            "developer@example.test", "Test", "body",
            template_id="test", idempotency_key="test-event",
        )


def test_missing_provider_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(email_service.settings, "resend_api_key", "")
    monkeypatch.setattr(email_service.settings, "resend_from_email", "")
    monkeypatch.setattr(email_service.settings, "smtp_host", "")
    monkeypatch.setattr(email_service.settings, "smtp_from_email", "")

    with pytest.raises(RuntimeError, match="not configured"):
        email_service.send_transactional_email(
            "developer@example.test", "Test", "body", template_id="test",
        )
