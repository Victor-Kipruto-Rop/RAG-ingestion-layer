# Environment-scoped API keys

## Security contract

- Every user-issued key belongs to exactly one organization and one environment: `sandbox` or `production`.
- Sandbox keys are accepted only by an API deployment configured with `API_ENVIRONMENT=sandbox`. A sandbox key used against production is rejected with HTTP 403 and error code `API_KEY_ENVIRONMENT_MISMATCH`; the attempt is persisted as an audit/security event and logged without the secret.
- Production keys are accepted only by a deployment configured with `API_ENVIRONMENT=production`.
- A request header, query parameter, or client-supplied environment label never overrides the server's `API_ENVIRONMENT`.
- Key secrets are generated with a cryptographically secure random generator, stored only as SHA-256 hashes, shown once, and never returned by list endpoints.
- Key management requires a short-lived, trusted PesaGuard-issued HS256 JWT with `sub`, `org_id`, `exp`, `roles`, and (for production key creation) `organization_verified: true`. JWT issuer and audience are checked when configured. Do not mint user tokens from browser input.
- Production key creation requires the JWT to state that the organization is verified and the user has an `owner` or `admin` role. The identity provider must set these claims based on its authoritative records, not client-submitted form fields.
- Key management routes are organization-scoped. Users cannot list, rotate, or revoke another organization's keys by changing an ID.
- Rotation revokes the old key and returns a new secret once. Revocation is immediate for subsequent requests.

## Deployment configuration

Set these server-side variables (never in Vite/browser variables):

- `API_ENVIRONMENT=production` on the live API service.
- `API_ENVIRONMENT=sandbox` on a separate sandbox service with a separate sandbox database, storage bucket/prefix, credentials, and hostname.
- `API_KEY_AUTH_JWT_SECRET`: high-entropy shared secret used by the trusted PesaGuard identity service to sign HS256 access tokens.
- `API_KEY_AUTH_JWT_ISSUER` and `API_KEY_AUTH_JWT_AUDIENCE`: configure to the exact identity provider issuer and audience.
- Continue using `REGISTRY_API_KEYS` only for existing trusted internal service-to-service callers during migration. Never expose it to browser JavaScript or customer API consumers.

Production and sandbox should be separate deployments. Setting a frontend dropdown or sending `X-Environment: production` is not environment isolation. The API environment comes from deployment configuration. Do not point the sandbox deployment at production PostgreSQL or production object storage.

## Migration / rollout

1. Apply `database/migrations/009_environment_scoped_api_keys.sql` to the database.
2. Configure the JWT secret and matching issuer/audience on the API deployment and identity issuer.
3. Set `API_ENVIRONMENT=production` on production and provision an isolated sandbox deployment/database/storage.
4. Configure PesaGuard's trusted identity provider to issue short-lived JWTs with verified `sub`, `org_id`, roles and verification claims.
5. Test sandbox key on production (403 and audit event), production key on sandbox (403 and audit event), expired/revoked keys (401), cross-organization management (404), unverified organization production-key creation (403), and one-time secret display.
6. Only then expose key management in the customer dashboard.

The legacy static `REGISTRY_API_KEYS` remain internal service credentials and are not managed by this feature. Rotate/migrate them separately; do not treat them as customer-issued keys.

## Customer key scope model (updated)

Customer-issued keys are **read-only lookup credentials**. The only scopes that can be granted are
`registry:read` (lookup, search and organization listing) and `sources:read` (source catalogue).

Customer keys can never reach ingestion, uploads, bulk export, metrics, warehouse telemetry or source
writes, whatever scopes a legacy key row carries: those endpoints return `403 API_KEY_ENDPOINT_NOT_AVAILABLE`.
Ingestion writes into the shared canonical registry and job data is not tenant-scoped, so it stays internal.
Responses to customer keys mask tax PINs (last two characters only) and redact PIN/tax fields in
`registry_payload`.

Rotation is atomic: the old key is revoked and the replacement issued in one transaction. If the
replacement is refused (for example the organization is no longer verified) the old key keeps working.
Rotation drops any legacy scope outside the allowed set.
