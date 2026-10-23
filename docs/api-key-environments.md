# Managed API keys: sandbox and production

## Security model

Managed keys are environment-bound. A sandbox key is accepted only by a Datasource deployment configured with `DATASOURCE_ENVIRONMENT=sandbox` (or local development, which maps to sandbox). A production key is accepted only by a deployment configured with `DATASOURCE_ENVIRONMENT=production`. The server deployment setting is authoritative; request headers cannot change the environment.

Keys use the `pg_sandbox_` and `pg_live_` prefixes. Only a SHA-256 digest and a short lookup prefix are persisted; the full secret is returned once at creation or rotation. Never place API keys or the key-management token in React build variables, source control, logs, or chat.

## Required configuration

- `KEY_MANAGEMENT_TOKEN`: a long random secret used only by a trusted operator/server-side client to create, list, rotate, revoke and inspect key security events.
- `DATASOURCE_ENVIRONMENT`: `development`, `sandbox`, or `production`.
- `REGISTRY_API_KEYS`: existing legacy shared keys can remain during a controlled migration. They are not managed keys and do not have per-key scope/expiry/revocation. Remove them only after all callers have migrated and the rollback plan is approved.

Do not expose the management token to the dashboard browser. This repository currently has no end-user identity/session system, so these endpoints are operator-only; customer self-service key management must be connected to authenticated user/organization membership before it is exposed in the UI.

## Migration

Review and apply `database/migrations/009_managed_api_keys.sql` to the intended database through the approved migration process. The application does not run this migration automatically. Do not test by modifying production data.

## Operator endpoints

All endpoints below require `X-Key-Management-Token` and HTTPS:

- `GET /api/v1/admin/api-keys?environment=sandbox` — list metadata; secrets are never returned.
- `POST /api/v1/admin/api-keys` — create a key.
- `POST /api/v1/admin/api-keys/{key_id}/rotate` — revoke the old key and return a replacement once.
- `POST /api/v1/admin/api-keys/{key_id}/revoke` — revoke a key.
- `GET /api/v1/admin/api-keys/security-events` — view environment mismatches, revoked/expired-key attempts, and denied scopes.

Example create body:

```json
{
  "name": "PesaGuard staging integration",
  "environment": "sandbox",
  "scopes": ["registry:read", "ingestion:write"],
  "expires_in_days": 90
}
```

Use a trusted server-side operator client to call the endpoints; do not paste real tokens into shell history or shared logs.

## Environment mismatch behavior

A sandbox key presented to production receives HTTP 403 with code `API_KEY_ENVIRONMENT_MISMATCH`. The event records the key ID/prefix, actual server environment, endpoint, and correlation ID. The secret is never recorded. Production keys presented to sandbox are also rejected.

## Scopes

- `registry:read`: read registry, source, job, metrics, export and warehouse endpoints.
- `ingestion:write`: upload/complete ingestion and create/update registry source metadata.

A key without the required scope receives HTTP 403 `API_KEY_SCOPE_DENIED`. Add narrowly scoped keys rather than sharing one key across unrelated integrations.
