"""Provider adapter contracts for future registry integrations.

Adapters deliberately report NOT_CONFIGURED until credentials, permission, contract,
and purpose-of-use approval have been supplied. No network call or mock verification
is performed by this module.
"""
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    status: str
    configured: bool
    verified: bool = False
    data: dict[str, Any] = field(default_factory=dict)
    evidence_reference: str | None = None
    message: str = ""


class RegistryProvider(Protocol):
    name: str

    def lookup_registration(self, registration_number: str) -> ProviderResult:
        """Return a provider response without treating missing data as a failed identity check."""
        ...


class NotConfiguredProvider:
    """Safe placeholder that never pretends a government/commercial API is connected."""

    def __init__(self, name: str, purpose: str):
        self.name = name
        self.purpose = purpose

    def lookup_registration(self, registration_number: str) -> ProviderResult:
        value = (registration_number or "").strip()
        if not value:
            return ProviderResult(
                provider=self.name, status="INVALID_INPUT", configured=False,
                message="A registration number is required.",
            )
        return ProviderResult(
            provider=self.name, status="NOT_CONFIGURED", configured=False,
            message=f"{self.name} adapter is not connected. {self.purpose}",
        )


# Replace these adapters only after provider approval, credentials and contract tests.
BRS_PROVIDER = NotConfiguredProvider(
    "Kenya Business Registration Service",
    "Obtain approved API access, permitted purpose, and data-processing terms first.",
)
KRA_PROVIDER = NotConfiguredProvider(
    "Kenya Revenue Authority",
    "Use only an approved KRA integration and never infer PIN validity from imported data.",
)
