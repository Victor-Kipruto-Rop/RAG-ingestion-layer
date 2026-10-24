import hashlib
import hmac

import pytest

from pesaguard import PesaGuardClient, PesaGuardError, verify_webhook_signature


def test_sandbox_and_production_key_prefixes_are_not_interchangeable():
    with pytest.raises(ValueError, match="pg_live_"):
        PesaGuardClient("pg_sandbox_test", environment="production")
    with pytest.raises(ValueError, match="pg_sandbox_"):
        PesaGuardClient("pg_live_test", environment="sandbox")


def test_known_opposite_environment_base_url_is_rejected():
    with pytest.raises(ValueError, match="environment does not match"):
        PesaGuardClient("pg_live_test", environment="production", base_url="https://sandbox-api.pesaguard.co.ke")


def test_search_sends_key_and_bounded_query():
    class Response:
        ok = True
        status_code = 200
        text = ""
        def json(self):
            return {"items": [], "count": 0}

    class Session:
        def __init__(self):
            self.call = None
        def get(self, url, **kwargs):
            self.call = (url, kwargs)
            return Response()
        def close(self):
            pass

    session = Session()
    client = PesaGuardClient("pg_sandbox_test", session=session)
    result = client.search("  Example  ", limit=5)

    assert result["count"] == 0
    url, kwargs = session.call
    assert url == "https://sandbox-api.pesaguard.co.ke/api/v1/registry/search"
    assert kwargs["params"] == {"q": "Example", "limit": 5}
    assert kwargs["headers"]["X-API-Key"] == "pg_sandbox_test"
    assert kwargs["allow_redirects"] is False


def test_lookup_requires_exactly_one_identifier():
    client = PesaGuardClient("pg_sandbox_test")
    with pytest.raises(ValueError, match="exactly one"):
        client.lookup()
    with pytest.raises(ValueError, match="exactly one"):
        client.lookup(registration_number="R1", tax_pin="P1")
    client.close()


def test_webhook_signature_checks_raw_bytes_and_replay_window():
    secret = "whsec_test_secret"
    payload = b'{"id":"evt_1","type":"webhook.test"}'
    timestamp = 1_800_000_000
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={digest}"

    assert verify_webhook_signature(payload, header, secret, now=timestamp)
    assert not verify_webhook_signature(payload + b" ", header, secret, now=timestamp)
    assert not verify_webhook_signature(payload, header, secret, now=timestamp + 301)
    assert not verify_webhook_signature(payload, "t=bad,v1=bad", secret, now=timestamp)


def test_http_error_preserves_status_and_body():
    class Response:
        ok = False
        status_code = 403
        text = '{"detail":"forbidden"}'
        def json(self):
            return {"detail": "forbidden"}

    class Session:
        def get(self, *_args, **_kwargs):
            return Response()
        def close(self):
            pass

    client = PesaGuardClient("pg_sandbox_test", session=Session())
    with pytest.raises(PesaGuardError) as exc:
        client.search("Example")
    assert exc.value.status_code == 403
    assert exc.value.response_body == {"detail": "forbidden"}
