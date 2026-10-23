# PesaGuard Datasource — production release and incident runbook

This runbook is a controlled checklist. Passing CI does not itself authorize a production release. Do not run migrations, change Render/Supabase/R2 settings, reprocess production jobs, or deploy without explicit service-owner approval.

## 1. Pre-release gate

- [ ] Confirm the target commit, reviewed pull request, and release owner.
- [ ] Confirm required GitHub Actions jobs pass: backend tests, Ruff, Alembic disposable-database smoke test, frontend tests/build, API/worker/frontend container builds, and security scans.
- [ ] Review dependency and secret-scan findings; resolve high/critical findings or record an explicitly approved exception with an expiry date.
- [ ] Confirm a recent database backup exists and the restore procedure has been tested.
- [ ] Review SQL migrations and Alembic revisions side-by-side. Never stamp an existing database or apply both migration paths blindly.
- [ ] Confirm required environment variables exist in the secret manager. Do not print or paste values into logs or pull requests.
- [ ] Confirm the target environment is explicit: `API_ENVIRONMENT=sandbox` or `API_ENVIRONMENT=production`.
- [ ] Confirm production frontend build uses the correct `VITE_API_BASE_URL`; never place a server-only key in a `VITE_*` variable.
- [ ] Confirm the configured CORS origins are exact HTTPS origins, not wildcard origins.
- [ ] Confirm health-check path and expected readiness dependencies with the deployment owner.

## 2. Environment and secrets

Required production configuration depends on the selected deployment features. Review `example.env` and `docs/internal-api-security.md`.

- Keep `REGISTRY_API_KEYS`, JWT signing secret, HMAC secret, database URL, Redis URL, R2 credentials, and metrics token server-side.
- Use separate credentials and data stores for sandbox and production wherever possible.
- Do not enable `REQUIRE_HMAC` until all callers implement the documented canonical request signature and Redis-backed nonce replay protection is healthy.
- API-key management requires a PesaGuard-issued JWT. Configure the same issuer, audience, and signing secret as the trusted identity service. If the datasource cannot verify that identity token, key management must remain unavailable.
- Rotate compromised credentials; do not revoke an active integration until the replacement credential has been safely delivered and its cutover coordinated, except during an active compromise.

## 3. Migration procedure

1. Identify the exact migration files to apply and their order.
2. Take a backup or snapshot and record the backup identifier.
3. Restore that backup to a disposable staging database.
4. Apply the proposed migration sequence to staging; run schema checks and targeted integration tests.
5. Verify existing row counts, key uniqueness, foreign-key integrity, and critical indexes before and after.
6. Schedule the production change window and announce expected impact.
7. Apply only the approved migration commands using the trusted operator environment.
8. Verify readiness, API authentication, lookup, ingestion queue visibility, and dashboard connectivity.
9. Record the applied revision, operator, time, backup identifier, and validation results.
10. If checks fail, stop processing and follow the rollback/recovery procedure. Do not improvise destructive down-migrations.

## 4. Post-release smoke checks

Use read-only requests first. Never use real confidential documents as smoke-test fixtures.

- `GET /health/live` should return a successful liveness response.
- `GET /health/ready` should return success only when the database readiness check passes.
- `GET /health` should accurately describe available dependencies without returning credentials.
- `GET /docs` should be reachable only as permitted by the deployment's exposure policy.
- `GET /metrics` must remain protected by `X-Metrics-Token` or disabled.
- Verify an invalid API key is rejected.
- In a sandbox deployment, verify a sandbox key succeeds on an authorized read-only route.
- Verify a sandbox key against production is rejected with `API_KEY_ENVIRONMENT_MISMATCH`. Use a controlled test credential and confirm the event is recorded without storing the raw secret.
- Verify the dashboard reports API errors and processing states truthfully.
- Check recent logs for unexpected 5xx errors, queue growth, failed jobs, database connection exhaustion, or object-storage failures.

## 5. Incident response

### Suspected API-key leak
1. Identify the key ID/prefix and affected environment from audit events; never search for or copy the raw secret into chat.
2. Revoke the affected key, or isolate the integration immediately if the compromise is active.
3. Issue a replacement with the minimum required scopes and expiry.
4. Deliver it through an approved secret manager/channel and verify the caller has switched.
5. Review access/audit logs from the earliest plausible exposure time; preserve relevant evidence.
6. Rotate related credentials if there is evidence they were exposed, and record the incident and remediation.

### Ingestion backlog or repeated failures
1. Check readiness, database connectivity, object storage access, worker health, queue depth, attempt count, and the job's correlation ID.
2. Inspect sanitized row errors and the job error summary; do not copy raw row payloads into tickets.
3. Confirm whether the object still exists and whether its checksum matches the recorded metadata.
4. Pause automatic retries only through an approved operational action if retrying is causing harm.
5. Fix the underlying issue, then retry only eligible jobs using the supported worker workflow.
6. Confirm row progress, idempotency, and warehouse counts before declaring recovery.

### Suspected bad import
1. Stop further imports from the affected source.
2. Preserve the job ID, source key, checksum, and audit records.
3. Determine the affected records using provenance and version history.
4. Prepare a reviewed correction/re-import plan; do not delete or overwrite rows directly without a rollback plan.
5. Validate the correction in staging, apply with approval, and verify source lineage.

## 6. Recovery and closeout

- Restore from a tested backup if the database cannot be repaired safely.
- Confirm R2 retention/versioning and access policies independently; application backups do not automatically back up stored objects.
- Record the incident timeline, customer impact, root cause, remediation, and follow-up tasks.
- Update the roadmap only when evidence exists. Do not mark a phase complete because code was merged; release checks and production verification are separate.