# Registry provider integration readiness

The Datasource exposes a read-only provider status endpoint and a provider result contract. It does **not** make live BRS, KRA, or Peleza calls, and must not imply that a company has been verified by those authorities.

## Required before a live adapter is enabled

1. Obtain written provider approval, permitted-use scope, rate limits, data-processing/retention terms, support contact and service-level expectations.
2. Confirm the actual endpoint contract, authentication flow, required headers, request/response schemas, error codes, idempotency rules and sandbox environment from the provider's current documentation.
3. Store credentials only in the deployment secret manager; never in frontend variables, fixtures, source code or logs.
4. Implement a provider-specific adapter using the existing RegistryProvider and ProviderResult contract in backend/src/providers/base.py. Normalize responses into explicitly sourced evidence; preserve provider reference and check timestamp where permitted.
5. Use bounded retries only for transient failures, circuit breaking, request timeouts, correlation IDs and a provider-specific rate limit. Do not retry business rejections or turn timeouts into a negative verification result.
6. Return unavailable or manual_review if provider checks cannot be completed. Never substitute a local registry match or a guessed response for provider confirmation.
7. Add contract tests with provider-approved sandbox fixtures and tests for timeout, throttling, malformed response, expired credentials and provider outage.
8. Obtain security/privacy review and a release owner approval before enabling the adapter in production.

## Current status endpoint

GET /api/v1/providers/status reports not_connected for BRS, KRA and Peleza. It reports only whether the named configuration variables are present; that does not mean credentials are valid or that the provider is reachable. It does not transmit data externally.

## Current boundary

The service supports internal registry lookup and evidence review. It is not an authority, and its imported data or fuzzy matching is not proof of current legal status, tax compliance, beneficial ownership, or identity.
