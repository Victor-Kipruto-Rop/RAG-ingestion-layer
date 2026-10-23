"""Registry provider registry with safe, explicit not-configured defaults."""
from .base import ProviderResult, RegistryProvider

_PROVIDER_CATALOG = (
    ("brs", "Kenya Business Registration Service", ("business_registration", "organization_profile")),
    ("kra", "Kenya Revenue Authority", ("tax_pin", "taxpayer_status")),
    ("peleza", "Peleza", ("business_registration", "organization_profile")),
)

class ProviderRegistry:
    def __init__(self, adapters: tuple[RegistryProvider, ...] = ()):
        self._adapters = {adapter.key: adapter for adapter in adapters}

    def statuses(self) -> list[dict]:
        result = []
        for key, name, capabilities in _PROVIDER_CATALOG:
            adapter = self._adapters.get(key)
            result.append({
                "key": key,
                "display_name": name,
                "capabilities": list(capabilities),
                "status": "CONFIGURED" if adapter else "NOT_CONFIGURED",
                "live_checks_enabled": bool(adapter),
            })
        return result

    def check(self, provider_key: str, *, registration_number: str | None = None, tax_pin: str | None = None) -> ProviderResult:
        adapter = self._adapters.get(provider_key.strip().lower())
        if adapter is None:
            catalog_entry = next((item for item in _PROVIDER_CATALOG if item[0] == provider_key.strip().lower()), None)
            name = catalog_entry[1] if catalog_entry else provider_key[:100]
            return ProviderResult(
                provider=name,
                status="NOT_CONFIGURED",
                reason_code="PROVIDER_NOT_CONFIGURED",
                message="No verified provider adapter is configured. No external check was performed.",
            )
        try:
            result = adapter.check(registration_number=registration_number, tax_pin=tax_pin)
            if result.provider != adapter.display_name:
                raise ValueError("Provider adapter returned an unexpected provider identity")
            return result
        except TimeoutError:
            return ProviderResult(provider=adapter.display_name, status="UNAVAILABLE", reason_code="PROVIDER_TIMEOUT", message="Provider timed out; manual review is required.")
        except Exception:
            # Do not return exception text: it may contain credentials or personal data.
            return ProviderResult(provider=adapter.display_name, status="ERROR", reason_code="PROVIDER_CHECK_FAILED", message="Provider check failed; no verification decision was made.")

def default_provider_registry() -> ProviderRegistry:
    # No provider credentials or endpoint contracts are assumed. Register real adapters
    # only after credentials, permitted use, request schemas and response semantics are verified.
    return ProviderRegistry()
