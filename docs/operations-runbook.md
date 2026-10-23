# Operations runbook

This runbook covers routine diagnosis for PesaGuard Registry Datasource. It is intentionally read-only by default. Do not replay, delete, requeue, or modify production ingestion jobs as part of diagnosis without an approved incident action.

## 1. Initial triage

1. Record the incident start time, affected base URL/environment, request path, HTTP status, and `X-Correlation-ID` response header.
2. Check `GET /health/live` for process liveness.
3. Check `GET /health/ready` for database readiness.
4. Check `GET /health` for the combined basic status.
5. If authenticated access is available, inspect ingestion job state and the most recent failed-job summary. Do not copy API keys, presigned upload URLs, raw tax PINs, or full uploaded rows into tickets.
6. Use structured logs and correlation IDs to follow the request into ingestion worker logs.

The health endpoints currently verify process/database state and expose whether R2 is configured. They do not prove that a full upload, queue worker, Redis, or external provider is healthy. Treat a healthy HTTP response as a narrow signal, not end-to-end certification.

## 2. Common symptoms

### API returns 401
- Confirm the caller sends `X-API-Key` or the configured signed-request headers.
- Confirm the key is active, not expired, and copied completely.
- Never paste the secret into logs or chat. Check the key prefix and metadata through the operator key-management API.

### API returns 403 `API_KEY_ENVIRONMENT_MISMATCH`
- The key environment and server deployment environment differ.
- Use the matching base URL and key. Do not attempt to override the environment with a request header.
- Review `GET /api/v1/admin/security-events` for the event and correlation ID.

### API returns 403 `API_KEY_SCOPE_DENIED`
- Grant only the specific scope needed by the integration. Do not solve a scope error by automatically issuing an all-access key.

### Upload is queued but not progressing
- Check whether the independent worker is running and can access the same database and private object store.
- Confirm the object key exists in the configured private R2 bucket.
- Inspect persisted job status, attempts, `next_attempt_at`, `last_processed_row`, and the error summary.
- PDFs may finish as `NEEDS_PDF_PROCESSING`; this is an intentional manual-review state, not a successful structured-data import.

### Redis is unavailable
- In production with Redis configured, the distributed rate limiter fails closed if its Redis dependency is unavailable. Investigate Redis connectivity before retrying.
- Cache reads are best-effort and the database remains authoritative. Do not infer a database outage from cache misses alone.

### Database schema mismatch
- Capture the exact missing column/table name and the deployed code revision.
- Compare the deployed schema with the numbered SQL migration history and Alembic revision.
- Do not run `alembic upgrade head`, stamp a revision, or apply SQL directly to production until the current schema has been reviewed and a migration plan approved.

## 3. Security incident response

1. Revoke the affected managed API key if compromise is suspected.
2. Rotate the key and update the server-side consumer secret store.
3. Review security events for environment mismatch, invalid keys, and scope denials.
4. Check logs for request IDs and key prefixes only; never log or retain the full key.
5. Preserve relevant audit records and follow the organization's incident and data-protection procedures.

## 4. Alerting candidates (configure in the monitoring platform)

- Any sustained increase in 5xx responses or p95/p99 request latency.
- Repeated `API_KEY_ENVIRONMENT_MISMATCH`, invalid-key, or scope-denial events.
- Queue depth rising while completed-job count remains flat.
- Repeated worker failures, retry exhaustion, or dead-letter growth.
- Database readiness failures or connection pool timeouts.
- Redis failures when distributed rate limiting is configured.
- Source freshness exceeding the source's configured freshness SLA.

Thresholds must be calibrated from representative load tests and operational baselines. No uptime or latency SLA is claimed by this repository alone.

## 5. Recovery and rollback

- Prefer a forward fix for schema changes; key and audit tables are intentionally protected from automated destructive downgrade.
- Before schema changes, take and verify an approved backup or staging snapshot.
- For a release rollback, use the previous known-good application image only if it is compatible with the current schema.
- Never delete security-event history to make an incident disappear.
- Verify health, a sandbox request, and a sandbox ingestion workflow before requesting production release approval.
