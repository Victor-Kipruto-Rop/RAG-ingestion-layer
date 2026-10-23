"""Provider adapter contract. Actual BRS/KRA/commercial connectors require approved credentials.
Adapters return evidence states and never silently certify a legal entity.
"""
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass
class ProviderResult:
    provider: str
    status: str  # match, no_match, pending, unavailable, manual_review
    matched: bool | None = None
    normalized_data: dict[str, Any] = field(default_factory=dict)
    evidence_reference: str | None = None
    checked_at: str | None = None
    message: str | None = None

class RegistryProvider(Protocol):
    name: str
    async def lookup_registration(self, registration_number: str) -> ProviderResult: ...

class ProviderNotConfigured(RuntimeError):
    pass
