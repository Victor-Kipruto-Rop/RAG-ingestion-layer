from src.api import _mask_payload, _mask_pin
from src.security import requires_lookup_rate_limit


def test_customer_payload_redaction_handles_nested_personal_and_credential_fields():
    payload = {
        "company_type": "limited",
        "tax_pin": "P000000000X",
        "director": {"full_name": "Private Person", "national_id": "12345678"},
        "contacts": [{"business_email": "person@example.invalid", "phone_number": "+254700000000"}],
        "credentials": {"api_token": "never-return-this"},
        "registry_reference": "public-reference-1",
    }

    result = _mask_payload(payload)

    assert result["company_type"] == "limited"
    assert result["tax_pin"] == "[REDACTED]"
    assert result["director"] == "[REDACTED]"
    assert result["contacts"] == [{"business_email": "[REDACTED]", "phone_number": "[REDACTED]"}]
    assert result["credentials"] == "[REDACTED]"
    assert result["registry_reference"] == "public-reference-1"


def test_customer_payload_redaction_is_safe_for_unexpected_payload_shapes():
    assert _mask_payload(None) == {}
    assert _mask_payload(["unexpected", {"email": "private"}]) == {}


def test_pin_masking_retains_only_last_two_characters():
    assert _mask_pin("P051234567A") == "*********7A"
    assert _mask_pin(None) is None
    assert _mask_pin("") == ""


def test_registry_record_enumeration_paths_are_rate_limited():
    assert requires_lookup_rate_limit("/api/v1/registry/lookup")
    assert requires_lookup_rate_limit("/api/v1/registry/search")
    assert requires_lookup_rate_limit("/api/v1/organizations")


def test_non_enumeration_paths_do_not_use_lookup_rate_limit_bucket():
    assert not requires_lookup_rate_limit("/api/v1/health")
    assert not requires_lookup_rate_limit("/api/v1/sources")
