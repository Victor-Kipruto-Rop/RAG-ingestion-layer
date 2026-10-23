# API Key Lifecycle

## Environment boundary
The server deployment's `PESAGUARD_DATASOURCE_ENVIRONMENT` is authoritative. A request header, query parameter, or browser selector must never change the environment being accessed. A sandbox key presented to a production deployment must return HTTP 403 with code `API_KEY_ENVIRONMENT_MISMATCH`; record a security event containing the key ID/prefix, endpoint, request ID, expected environment, and key environment. Never record the raw secret.

## Key format and storage
Generate a high-entropy random secret with a prefix such as `pg_sandbox_` or `pg_live_`. Display the full secret only in the create/rotate response. Store only SHA-256(secret), prefix, metadata, and scopes. Use cryptographically secure randomness, constant-time comparisons, and no raw-secret logging.

## Lifecycle
- Create validates name, environment, allowed scopes, and optional expiration; returns the secret once.
- List returns metadata only, never the digest or secret.
- Revoke immediately disables a key and records an audit event.
- Rotate creates a replacement, revokes its predecessor transactionally, and returns the new secret once.
- Expired/revoked keys are rejected; scopes are enforced by backend routes.
- Environment mismatches return a stable machine-readable error and persist a security event.

## Management authentication boundary
The current API uses shared service API keys and does not establish a verified human user or organization-owner identity. Until authenticated tenant sessions and roles are integrated, management routes must use a separate server-side management credential and must not be called directly by browser clients. Never trust a caller-supplied organization/tenant ID as proof of ownership. Never put the management credential in a `VITE_*` variable.

## Rollout
1. Apply and verify the additive migration in a non-production database.
2. Configure `PESAGUARD_DATASOURCE_ENVIRONMENT=sandbox` or `production` on each deployment.
3. Configure the management credential only on a trusted server-side operator path.
4. Test sandbox keys and verify production rejects them with an audited mismatch.
5. Migrate callers, then revoke legacy shared keys only after verified rollout.
6. Keep production migration and deployment approval explicit.
