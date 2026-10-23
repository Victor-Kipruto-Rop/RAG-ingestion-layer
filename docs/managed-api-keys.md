# Managed API keys

Managed API keys are intended for server-to-server datasource integrations. They are distinct from the legacy `REGISTRY_API_KEYS` compatibility path.

## Environments

- Sandbox credentials use the `pg_sandbox_` prefix.
- Production credentials use the `pg_live_` prefix.
- Set `DATASOURCE_ENVIRONMENT=sandbox` on sandbox deployments and `DATASOURCE_ENVIRONMENT=production` on production deployments. If unset, the service falls back to `APP_ENV` (`production` maps to production; other values map to sandbox).
- The server's environment configuration is authoritative. A request header or body cannot switch the environment.
- If a managed key is used against the wrong environment, the API returns HTTP 403 with code `API_KEY_ENVIRONMENT_MISMATCH` and records a security event. Do not retry by changing headers; use the correct key and base URL.
- Sandbox and production should be separate deployment environments with separate secrets, databases, and data-access policies. A prefix is not a substitute for infrastructure isolation.

## Creating and managing keys

The operator-only routes are protected by the server-side `DATASOURCE_ADMIN_TOKEN`:

- `GET /api/v1/admin/api-keys` — list metadata (never returns full secrets).
- `POST /api/v1/admin/api-keys` — create a key. The full secret is returned once.
- `POST /api/v1/admin/api-keys/{key_id}/rotate` — create a replacement and revoke the old key immediately.
- `DELETE /api/v1/admin/api-keys/{key_id}` — revoke a key.
- `GET /api/v1/admin/security-events` — review invalid-key, wrong-environment and scope-denial events.

Send the admin token as `Authorization: Bearer <token>`. Never expose it in public frontend source, commit it, put it in browser local storage, or use it as an integration API key. The dashboard's key-management form keeps the token in page memory only; for a multi-user customer-facing key portal, replace operator-token access with authenticated user identity, organization membership, and role-based authorization before exposing key management to tenants.

## Storage and rotation

Only a SHA-256 digest of the high-entropy random secret is stored. The full secret is returned only at creation/rotation and cannot be recovered later. Store it in a server-side secret manager. Rotation revokes the previous key immediately, so coordinate the client update to avoid downtime. Choose a short expiry for temporary credentials and revoke unused keys.

## Scope permissions

- `registry:read`: registry, quality, and warehouse reads.
- `ingestion:write`: create/complete ingestion uploads.
- `sources:write`: mutate registry source configuration.
- `exports:read`: export organization data.

Grant the minimum scopes needed. Legacy shared keys remain enabled only as a migration compatibility path; they do not provide the same per-key environment/scope controls. Plan their removal only after every caller has moved to managed keys and the cutover is explicitly approved.

## Database migration

For fresh disposable databases, run the repository's Alembic migrations from `backend/`:

```sh
python -m alembic -c alembic.ini upgrade head
```

For an existing database, do not run migrations or stamp Alembic until its schema has been compared with the SQL migration history and a reviewed migration plan exists. The equivalent SQL migration is `database/migrations/009_managed_api_keys.sql`; apply it only to the intended database with an approved change window.
