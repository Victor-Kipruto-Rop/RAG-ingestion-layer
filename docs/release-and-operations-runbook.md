# Release and Operations Runbook

This runbook is deliberately conservative: code in GitHub is not a production release. Never apply a production migration, change Render environment variables, rotate live credentials, or process queued production imports as a test without explicit approval from the service owner.

## 1. Pre-release checklist

1. Confirm the release branch and pull request contain only the intended changes.
2. Require green backend tests, migration smoke test, Ruff checks, frontend tests/build, container builds, CodeQL, dependency review, and secret scanning.
3. Review all new SQL/Alembic operations and compare them with the exact target database schema.
4. Confirm a recent backup exists and that the restoration procedure has been exercised against a disposable copy.
5. Confirm the API deployment's `API_ENVIRONMENT`, database, R2 bucket, CORS origins, JWT issuer/audience, and server-side secrets are correct. Never print secret values.
6. Verify the configured health-check path and expected readiness response.
7. Record the current deployment/version, migration revision, and rollback owner before rollout.

## 2. Migration safety

- Fresh disposable databases use `cd backend && python -m alembic -c alembic.ini upgrade head`.
- The hand-maintained SQL files under `database/migrations/` are a parallel legacy/Supabase path. Do not run the same logical migration through both paths on the same database.
- Existing databases must be inspected against the full schema baseline (tables, columns, indexes, constraints, views, extensions, grants, and RLS policies) before stamping or upgrading Alembic.
- Migration `0005_environment_scoped_api_keys` creates the customer API-key and audit tables for Alembic-managed installations. The SQL-only path has its corresponding migration `009_environment_scoped_api_keys.sql`.
- Do not run `stamp` or `upgrade head` on a live database merely to make CI pass. Back up first, use a restored staging copy, review differences, and obtain explicit approval.

## 3. Deployment and rollback

1. Deploy to an isolated staging/sandbox service with a separate database and storage location.
2. Apply the reviewed migration using the selected migration path.
3. Verify `/health/live`, `/health/ready`, and protected `/metrics`; confirm a sandbox key succeeds only in sandbox and is rejected in production.
4. Run fictional CSV ingestion through upload → queued job → worker → warehouse → lookup. Use a separate disposable database and bucket.
5. Inspect logs for correlation IDs, error categories, queue progress, and PII/secret leakage.
6. Promote only after review and approval. Do not route production traffic to a sandbox database.
7. If an application release fails, roll back the application image to the last known-good version while preserving additive schema changes. These migrations are intentionally forward-only; do not drop key/audit tables to roll back. Use a reviewed forward fix or restore a backup under the approved recovery plan.

## 4. API-key compromise

1. Revoke the affected key through the authenticated organization key-management endpoint.
2. Issue a replacement key with only the required scopes and a defined expiry.
3. Update the consuming secret store; never place the key in browser variables, chat, tickets, logs, or source control.
4. Check the organization's key audit events and service request logs by request/correlation ID. Audit events must never contain the raw key.
5. Check whether the key was used against the wrong environment and whether unexpected calls occurred.
6. Rotate any shared internal credential separately if it may also have been exposed. Plan migration away from legacy shared keys; they do not provide per-key environment isolation.

## 5. Ingestion incident and recovery

- Inspect the job's status, attempts, correlation ID, last committed row, source object metadata, and sanitized dead-letter records.
- Do not manually reset a job's status or delete failed-row evidence without a reviewed recovery plan.
- Retry only after confirming the cause is transient and the worker's idempotency/resume behavior applies.
- For PDFs, `NEEDS_PDF_PROCESSING` is a manual-review state, not a successful verified import. OCR output is not authoritative registry evidence.
- For files exceeding configured bounds, keep the source object private and use the documented manual-review or approved multipart workflow.

## 6. Backups, restore, and retention

- Maintain encrypted database backups and private object-storage retention rules appropriate to the data-processing agreement.
- Keep database backups and R2 object retention coordinated: restoring warehouse metadata without its raw object evidence may make a job unrecoverable.
- Exercise restoration on a separate disposable environment, verify row counts/checksums and key/audit history, then delete the test restore under the approved retention policy.
- Define a retention schedule for raw uploads, failed-row diagnostics, audit logs, and expired API keys before importing confidential registry datasets.

## 7. Monitoring and alerting

Create alerts in the actual monitoring platform for sustained 5xx rates, readiness failures, queue age/depth, repeated job failures, rate-limit spikes, API-key environment mismatch events, Redis outage when distributed controls are required, and storage upload failures. Alert thresholds must be tuned from staging/load-test evidence; no latency or availability SLA is claimed until measured.

## 8. External provider integration gate

Do not mark BRS, KRA, IPRS, or a commercial verification provider as connected until the provider contract, authorized purpose, credentials, rate limits, data-processing terms, timeout/retry rules, and response schema are approved. Until then, imported records remain source-attributed reference data and must not be presented as authoritative verification.
