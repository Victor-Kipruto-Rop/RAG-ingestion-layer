"""Safe provider contracts for future authoritative registry integrations.

No provider is treated as connected until a concrete adapter is configured and
its credentials/contract have been validated in a non-production environment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Protocol


class ProviderStatus(StrEnum):
    VERIFIED = "verified"
    NOT_FOUND = "not_found"
    MANUAL_REVIEW = "manual_review"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class ProviderResult:
    """Normalized provider outcome; not universal legal certification.

    The legacy fields remain available during migration so existing adapters can
    return normalized_data/evidence_reference while moving to the shared schema.
    """
    provider: str
    status: ProviderStatus | str
    matched: bool | None = None
    normalized_data: dict[str, Any] = field(default_factory=dict)
    evidence_reference: str | None = None
    checked_at: datetime | str | None = None
    message: str | None = None
    reference_id: str | None = None
    matched_fields: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    retryable: bool = False

    def __post_init__(self) -> None:
        raw_status = self.status.value if isinstance(self.status, ProviderStatus) else str(self.status).strip().lower()
        aliases = {
            "match": ProviderStatus.VERIFIED,
            "matched": ProviderStatus.VERIFIED,
            "no_match": ProviderStatus.NOT_FOUND,
            "not_found": ProviderStatus.NOT_FOUND,
            "pending": ProviderStatus.MANUAL_REVIEW,
            "manual_review": ProviderStatus.MANUAL_REVIEW,
            "verified": ProviderStatus.VERIFIED,
            "unavailable": ProviderStatus.UNAVAILABLE,
            "error": ProviderStatus.ERROR,
        }
        normalized = aliases.get(raw_status, ProviderStatus.ERROR)
        object.__setattr__(self, "status", normalized)
        if self.matched is None and normalized in {ProviderStatus.VERIFIED, ProviderStatus.NOT_FOUND}:
            object.__setattr__(self, "matched", normalized == ProviderStatus.VERIFIED)

    def to_dict(self) -> dict[str, Any]:
        checked_at = self.checked_at
        if checked_at is None:
            checked = datetime.now(timezone.utc)
        elif isinstance(checked_at, str):
            checked = checked_at
        else:
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=timezone.utc)
            checked = checked_at.isoformat()
        status = self.status.value if isinstance(self.status, ProviderStatus) else str(self.status)
        return {
            "provider": self.provider,
            "status": status,
            "matched": self.matched,
            "checked_at": checked,
            "reference_id": self.reference_id or self.evidence_reference,
            "matched_fields": self.matched_fields,
            "normalized_data": self.normalized_data,
            "evidence": self.evidence,
            "message": self.message,
            "retryable": self.retryable,
        }


class VerificationProvider(Protocol):
    name: str
    def check_registration(self, registration_number: str) -> ProviderResult: ...
    def check_tax_pin(self, tax_pin: str) -> ProviderResult: ...


class RegistryProvider(Protocol):
    name: str
    async def lookup_registration(self, registration_number: str) -> ProviderResult: ...


class ProviderNotConfigured(RuntimeError):
    pass


class UnconfiguredProvider:
    """Explicit unavailable adapter; it never fabricates a successful result."""
    def __init__(self, name: str, reason: str = "Provider integration is not configured"):
        self.name = name
        self.reason = reason

    def check_registration(self, registration_number: str) -> ProviderResult:
        return self._unavailable()

    def check_tax_pin(self, tax_pin: str) -> ProviderResult:
        return self._unavailable()

    async def lookup_registration(self, registration_number: str) -> ProviderResult:
        return self._unavailable()

    def _unavailable(self) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.UNAVAILABLE,
            message=self.reason,
            retryable=False,
        )


class ProviderRegistry:
    """Explicit registry that defaults to unavailable, never to mock success."""
    def __init__(self) -> None:
        self._providers: dict[str, VerificationProvider] = {}

    def register(self, provider: VerificationProvider) -> None:
        name = provider.name.strip().lower()
        if not name:
            raise ValueError("Provider name must not be empty")
        if name in self._providers:
            raise ValueError(f"Provider {name!r} is already registered")
        self._providers[name] = provider

    def get(self, name: str) -> VerificationProvider:
        normalized = name.strip().lower()
        return self._providers.get(normalized, UnconfiguredProvider(normalized or "unknown"))

    def names(self) -> list[str]:
        return sorted(self._providers)
