import pytest
from pydantic import ValidationError

from src.verification import VerificationCaseRequest, list_verification_providers


def test_provider_catalog_never_claims_live_verification_without_adapters():
    result = list_verification_providers()
    assert result["count"] == 3
    assert all(provider["status"] == "not_configured" for provider in result["items"])
    assert all(provider["live_enabled"] is False for provider in result["items"])
    assert "No external provider check is executed" in result["message"]


def test_verification_case_requires_at_least_one_subject_identifier():
    with pytest.raises(ValidationError):
        VerificationCaseRequest()


def test_verification_case_accepts_registration_number():
    request = VerificationCaseRequest(registration_number=" CPR-123 ")
    assert request.registration_number == " CPR-123 "
