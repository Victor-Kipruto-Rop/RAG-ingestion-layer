"""External registry-provider adapters; integrations stay disabled until configured."""
from .registry import ProviderRegistry, default_provider_registry

__all__ = ["ProviderRegistry", "default_provider_registry"]
