"""Stable contract for registry verification providers.

Provider responses are evidence, not a substitute for local authorization or a
human review policy. Adapters must not return VERIFIED without provider evidence.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

PROVIDER_STATUSES = {
    "VERIFIED", "NOT_VERIFIED", "REVIEW_REQUIRED", "NOT_CONFIGURED", "UNAVAILABLE", "ERROR"
}

@dataclass(frozen=True)
class ProviderResult:
    provider: str
    status: str
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence: dict[str, Any] = field(default_factory=dict)
    reason_code: str | None = None
    message: str = ""

    def __post_init__(self):
        if self.status not in PROVIDER_STATUSES:
            raise ValueError(f"Unsupported provider status: {self.status}")
        if self.status == "VERIFIED" and not self.evidence:
            raise ValueError("A VERIFIED provider result must include evidence")

class RegistryProvider(Protocol):
    key: str
    display_name: str
    capabilities: tuple[str, ...]

    def check(self, *, registration_number: str | None = None, tax_pin: str | None = None) -> ProviderResult:
        """Perform a provider-specific check and return normalized evidence."""
