from datetime import datetime

import pytest

from src.providers import ProviderRegistry, ProviderResult, ProviderStatus, UnconfiguredProvider


def test_unconfigured_provider_never_reports_a_positive_match():
    provider = UnconfiguredProvider("brs")
    registration = provider.check_registration("CPR/000000")
    tax_pin = provider.check_tax_pin("A000000000X")
    assert registration.status == ProviderStatus.UNAVAILABLE
    assert tax_pin.status == ProviderStatus.UNAVAILABLE
    assert registration.status != ProviderStatus.VERIFIED
    assert registration.retryable is False


def test_provider_registry_normalizes_names_and_defaults_closed():
    registry = ProviderRegistry()
    assert registry.names() == []
    assert registry.get("BRS").check_registration("CPR/000000").status == ProviderStatus.UNAVAILABLE

    class ExampleProvider:
        name = "example"

        def check_registration(self, registration_number):
            return ProviderResult(provider=self.name, status=ProviderStatus.MANUAL_REVIEW,
                                 matched_fields={"registration_number": registration_number})

        def check_tax_pin(self, tax_pin):
            return ProviderResult(provider=self.name, status=ProviderStatus.NOT_FOUND)

    registry.register(ExampleProvider())
    assert registry.names() == ["example"]
    assert registry.get("EXAMPLE").check_registration("CPR/1").status == ProviderStatus.MANUAL_REVIEW
    with pytest.raises(ValueError):
        registry.register(ExampleProvider())


def test_provider_result_serialization_normalizes_naive_timestamp():
    result = ProviderResult(provider="test", status=ProviderStatus.NOT_FOUND,
                            checked_at=datetime(2026, 1, 1),
                            evidence=[{"type": "response_reference", "value": "case-1"}])
    serialized = result.to_dict()
    assert serialized["status"] == "not_found"
    assert serialized["checked_at"].endswith("+00:00")
    assert serialized["evidence"][0]["type"] == "response_reference"


def test_legacy_provider_statuses_are_normalized_safely():
    positive = ProviderResult(provider="legacy", status="match")
    negative = ProviderResult(provider="legacy", status="no_match")
    pending = ProviderResult(provider="legacy", status="pending")
    unknown = ProviderResult(provider="legacy", status="some-unrecognized-status")
    assert positive.status == ProviderStatus.VERIFIED and positive.matched is True
    assert negative.status == ProviderStatus.NOT_FOUND and negative.matched is False
    assert pending.status == ProviderStatus.MANUAL_REVIEW
    assert unknown.status == ProviderStatus.ERROR
