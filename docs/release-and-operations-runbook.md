# Release and operations runbook

This runbook is for the PesaGuard Datasource service. It does not authorize a production release, database migration, or processing of production data. Run each release step with the service owner and preserve a rollback path.

## 1. Environment isolation

Run sandbox and production as separate service deployments. Set these server-side values on each deployment:

| Setting | Sandbox deployment | Production deployment |
| --- | --- | --- |
| `APP_ENV` | `development` or approved staging value | `production` |
| `DATASOURCE_ENVIRONMENT` | `sandbox` | `production` |
| `DATASOURCE_ADMIN_TOKEN` | Unique operator-only secret | Different unique operator-only secret |
| `DATABASE_URL` | Sandbox/test database | Production PostgreSQL/Supabase |
| `REGISTRY_API_KEYS` | Sandbox-only legacy key during migration | Production-only legacy key during migration |
| `R2_BUCKET_NAME` | Approved sandbox private bucket | Production private bucket |
| `REDIS_URL` | Optional sandbox instance | Approved shared production instance when required |

Do not rely on a request header or a user-selected dropdown to determine the environment. The server's `DATASOURCE_ENVIRONMENT` setting is authoritative. If unset, the service derives the environment from `APP_ENV`; production must explicitly set `DATASOURCE_ENVIRONMENT=production` to avoid ambiguity.

Managed keys have a `pg_sandbox_` or `pg_live_` prefix. The database stores only a SHA-256 digest of the high-entropy secret. The full secret is returned once by the create/rotate endpoint. Keep it in the caller's secret manager and never put it in a browser bundle, issue, screenshot, repository, or logs.

## 2. Managed API key lifecycle

1. Configure a strong `DATASOURCE_ADMIN_TOKEN` as a secret in the service environment.
2. Open the trusted operator dashboard over HTTPS and enter the token. Do not share it with customer tenants; the current key-management endpoint is operator-only, not tenant self-service.
3. Create a key in the correct environment and grant only required scopes.
4. Copy the returned secret immediately into the approved server-side secret manager. The dashboard intentionally does not persist the operator token or full API key.
5. Verify the integration using a non-sensitive test request against the matching environment.
6. Rotate a key by deploying the replacement to the caller as part of a coordinated change. Rotation immediately revokes the old key; ensure the caller can be updated before rotating.
7. Revoke compromised or retired keys, then inspect `/api/v1/admin/security-events` for environment mismatch and scope-denial events.
8. Do not treat legacy `REGISTRY_API_KEYS` as environment-isolated. During the migration period they remain compatible and must be configured separately on each deployment.

A sandbox key presented to a production deployment must return HTTP 403 with code `API_KEY_ENVIRONMENT_MISMATCH`, explain that the key is sandbox-only, and attempt to persist a security event. A scope failure returns `API_KEY_SCOPE_DENIED`. Never log the raw key.

## 3. Database migration checklist

1. Confirm the target database and environment independently; never use a production URL in local test commands.
2. Take a provider-supported backup or snapshot and verify the restore procedure.
3. Compare the current schema with all numbered scripts in `database/migrations/` and the Alembic revision chain. The SQL files and Alembic revisions must be reconciled before choosing one authoritative migration mechanism.
4. Review the exact SQL and expected lock/downtime impact.
5. Apply migrations to a disposable database, run the backend suite, and test upgrade from a schema snapshot matching the deployed database.
6. Obtain explicit release-owner approval before production migration. Apply during the approved window and verify table/index existence and application readiness afterward.
7. Do not apply migrations from application startup. Production startup intentionally does not auto-create tables.
8. Keep rollback instructions and a restore point available. For additive schema changes, prefer forward repair unless a tested rollback is safe for existing data.

## 4. Pre-release verification

From the repository root in an isolated environment:

```bash
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend DATABASE_URL=sqlite:///./ci_registry.db REGISTRY_API_KEYS=test-secret-key pytest -q
python -m compileall -q backend/src
cd frontend
npm install --no-audit --no-fund
npm test -- --run
npm run build
```

Run the same CI workflow on the exact proposed commit. A successful local run is not a substitute for CI, staging verification, or production smoke tests. Do not run ingestion uploads against production as a health check.

## 5. Safe smoke checks

- `GET /health/live` verifies the process is alive.
- `GET /health/ready` verifies database connectivity.
- `GET /health` reports service and database health plus whether R2 is configured; it does not prove that R2 can read/write.
- `GET /metrics` is only available with the configured `X-Metrics-Token`.
- Use a sandbox key only against the sandbox deployment and a production key only against production.
- Verify lookup/search responses, API key scope enforcement, key rotation/revocation, ingestion job state, and data-quality response shape with fictional fixtures.

## 6. Incident response

### Suspected key leak
1. Identify the key by prefix only; never paste the full secret into incident notes.
2. Revoke it through the operator endpoint or an approved database procedure if the management endpoint is unavailable.
3. Rotate the caller's secret and verify the new credential against the matching environment.
4. Review security events and service logs by request/correlation ID.
5. Check whether the key was committed to Git. If it was, revoke it immediately; deleting the latest file does not remove the secret from Git history.

### Queue or ingestion incident
1. Stop repeated retries if they are increasing load or duplicating work.
2. Inspect job status, attempt count, correlation ID, row progress, and sanitized dead-letter diagnostics.
3. Confirm object existence and retention state in private R2.
4. Resume only after identifying whether the job is safe to retry; do not manually reset row progress without a documented recovery procedure.

### Recovery
Document backup frequency, recovery-point objective, recovery-time objective, restore owner, and the last restore test before promising any availability or durability target.

## 7. Release record

Record for every production release:

- Commit SHA and pull request
- CI run URL and pass/fail result
- Migration IDs and approval
- Backup/snapshot identifier
- Render service and health-check path
- Smoke-test results and correlation IDs
- Rollback/forward-repair plan
- Release owner and timestamp

Never label the service production-ready solely because code exists on a branch.
