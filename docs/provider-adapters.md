# Registry provider adapters

## Current behavior
The datasource exposes:
- `GET /api/v1/providers/status` to report which adapters are registered.
- `POST /api/v1/providers/{provider_key}/check` to request a normalized check result and write a privacy-minimizing audit event.

The current default registry intentionally reports BRS, KRA and Peleza as `NOT_CONFIGURED`. No external network call is made, and the endpoint returns `PROVIDER_NOT_CONFIGURED`. This is deliberate: provider URLs, credentials, approved purposes, request/response schemas and legal permissions have not been supplied and verified in this repository.

## Adapter contract
Implement a provider-specific adapter satisfying `RegistryProvider`:
- `key`, `display_name`, and supported `capabilities`.
- `check(registration_number=..., tax_pin=...)` returns a normalized `ProviderResult`.
- Use explicit outcomes: `VERIFIED`, `NOT_VERIFIED`, `REVIEW_REQUIRED`, `NOT_CONFIGURED`, `UNAVAILABLE`, or `ERROR`.
- A `VERIFIED` result must include evidence. The API still marks `authoritative_verification: false`; a provider match must be interpreted under the approved verification policy.
- Never log API tokens, full identifiers, raw response bodies, or exception text. Preserve only safe reason codes and provider status in audit events.
- Use bounded timeouts, retry only retryable failures, respect provider rate limits, and use a circuit breaker before enabling production traffic.

## Before enabling a provider
1. Confirm contract, environment URLs, authentication and permissions with the provider.
2. Store credentials only in deployment secrets; never in React, source control, or logs.
3. Add adapter contract tests with sanitized fixtures and provider outage/timeout tests.
4. Validate response mapping and provenance; retain only data allowed for the stated purpose.
5. Use manual review when a response is missing, ambiguous, stale or unavailable.
6. Deploy first in a non-production environment and verify audit events/metrics before production approval.

No provider integration or production verification is activated by this change.
