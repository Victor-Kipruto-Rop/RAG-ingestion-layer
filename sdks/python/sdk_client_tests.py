import pytest
import hashlib
import hmac
import requests
import responses

from pesaguard import PesaGuardClient, PesaGuardError, verify_webhook_signature


def test_sandbox_key_uses_sandbox_host_and_header():
    with responses.RequestsMock() as mock:
        mock.add(responses.GET, "https://sandbox-api.pesaguard.co.ke/api/v1/registry/search",
                 json={"items": [], "count": 0}, status=200)
        client = PesaGuardClient("pg_sandbox_example", environment="sandbox")
        assert client.search("example")["count"] == 0
        assert mock.calls[0].request.headers["X-API-Key"] == "pg_sandbox_example"
        assert mock.calls[0].request.url.startswith("https://sandbox-api.pesaguard.co.ke/")


def test_production_key_cannot_be_used_as_sandbox_key():
    with pytest.raises(ValueError, match="must start"):
        PesaGuardClient("pg_live_example", environment="sandbox")


def test_sandbox_key_cannot_target_known_production_host():
    with pytest.raises(ValueError, match="does not match"):
        PesaGuardClient("pg_sandbox_example", environment="sandbox",
                        base_url="https://api.pesaguard.co.ke")


def test_lookup_requires_exactly_one_identifier():
    client = PesaGuardClient("pg_sandbox_example")
    with pytest.raises(ValueError, match="exactly one"):
        client.lookup()
    with pytest.raises(ValueError, match="exactly one"):
        client.lookup(registration_number="A", tax_pin="B")


def test_http_error_is_typed_and_response_body_is_preserved():
    with responses.RequestsMock() as mock:
        mock.add(responses.GET, "https://sandbox-api.pesaguard.co.ke/api/v1/registry/search",
                 json={"detail": "API_KEY_ENVIRONMENT_MISMATCH"}, status=403)
        client = PesaGuardClient("pg_sandbox_example")
        with pytest.raises(PesaGuardError) as exc:
            client.search("example")
        assert exc.value.status_code == 403
        assert exc.value.response_body["detail"] == "API_KEY_ENVIRONMENT_MISMATCH"


def test_webhook_signature_verification_accepts_valid_recent_payload():
    payload = b'{"id":"evt_1","type":"webhook.test"}'
    secret = "whsec_test_secret"
    timestamp = 1_800_000_000
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"
    assert verify_webhook_signature(payload, header, secret, now=timestamp)


def test_webhook_signature_verification_rejects_tampered_or_stale_payload():
    payload = b'{"id":"evt_1"}'
    secret = "whsec_test_secret"
    timestamp = 1_800_000_000
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={signature}"
    assert not verify_webhook_signature(payload + b" ", header, secret, now=timestamp)
    assert not verify_webhook_signature(payload, header, secret, now=timestamp + 1000)
