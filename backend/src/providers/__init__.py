"""Registry provider adapters with fail-closed defaults."""
from .base import (
    ProviderNotConfigured,
    ProviderRegistry,
    ProviderResult,
    ProviderStatus,
    RegistryProvider,
    UnconfiguredProvider,
    VerificationProvider,
)

__all__ = [
    "ProviderNotConfigured",
    "ProviderRegistry",
    "ProviderResult",
    "ProviderStatus",
    "RegistryProvider",
    "UnconfiguredProvider",
    "VerificationProvider",
]
