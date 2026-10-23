from src.providers.base import ProviderResult
from src.providers.registry import ProviderRegistry, default_provider_registry


def test_default_provider_registry_reports_disabled_providers_truthfully():
    statuses = default_provider_registry().statuses()
    assert {item["key"] for item in statuses} == {"brs", "kra", "peleza"}
    assert all(item["status"] == "NOT_CONFIGURED" for item in statuses)
    assert all(item["live_checks_enabled"] is False for item in statuses)


def test_check_on_unconfigured_provider_never_claims_verification():
    result = default_provider_registry().check("brs", registration_number="CPR-123")
    assert result.status == "NOT_CONFIGURED"
    assert result.reason_code == "PROVIDER_NOT_CONFIGURED"
    assert "No external check was performed" in result.message


def test_verified_result_requires_evidence():
    try:
        ProviderResult(provider="Example", status="VERIFIED", evidence={})
    except ValueError as exc:
        assert "must include evidence" in str(exc)
    else:
        raise AssertionError("A verified result without evidence must be rejected")
