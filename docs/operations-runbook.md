# PesaGuard Datasource Operations Runbook

This runbook is for service operators. It does not authorize production database changes or deployment by itself.

## Environments and secrets
- Keep sandbox and production in separate deployments and databases wherever possible.
- Set DATASOURCE_ENVIRONMENT=sandbox in sandbox and DATASOURCE_ENVIRONMENT=production in production. Never infer environment from a request header.
- Keep DATASOURCE_ADMIN_TOKEN server-side. Never put it in VITE variables, browser storage, frontend source, screenshots, or support tickets.
- REGISTRY_API_KEYS is a legacy compatibility path; legacy shared keys do not have per-key environment isolation. Migrate clients to managed keys before disabling legacy authentication.
- Configure Redis for shared rate limiting and distributed HMAC nonce protection. Per-process fallback does not protect across instances.
- Keep R2 private and scope credentials to required operations.

## Release checklist
1. Inspect the complete diff and target branch.
2. Run backend tests, Ruff, frontend tests, frontend production build, and migration tests on a disposable database.
3. Review dependency, secret, and container scan findings.
4. Back up the target database and document the restore point.
5. Compare ordered migrations with the live schema using read-only inspection.
6. Obtain explicit approval for production migrations and deployments.
7. Apply migrations through the approved release process; do not mutate production schema at application startup.
8. Deploy to sandbox first. Test health, auth, upload preview, a fictional CSV import, quality summary, and dashboard rendering.
9. Promote only after reviewing logs, error rates, queue depth, and database health.

## Health and triage
- /health/live indicates process liveness, not full dependency health.
- /health/ready reports readiness and required dependency checks.
- /metrics must be protected with the configured metrics token and restricted network access.
- Use request/correlation IDs to connect API logs, jobs, and warehouse access telemetry.
- Never log raw API keys, Authorization headers, full tax identifiers, document contents, or full request bodies.

### API returns 401
Check the authentication header, key expiry/revocation, and whether the managed-key migration is applied. Never paste a key into logs or issues.

### API returns 403 API_KEY_ENVIRONMENT_MISMATCH
The key belongs to the other environment. Use a sandbox key only with sandbox and production only with production. Do not bypass this by changing request headers.

### API returns 403 API_KEY_SCOPE_DENIED
Create or rotate a key with only the additional scope needed. Avoid granting every scope to every integration.

### Ingestion is stuck or repeatedly failing
Inspect status, attempts, progress, sanitized error summary, correlation ID, worker health, queue, database, and R2 object existence. Check stale leases before retrying; do not edit job rows while a worker may hold a lease. Preserve failure evidence and verify final counts and provenance after retry.

### R2 upload failure
Check bucket name, endpoint, credentials, permissions, content length, and object signature. Do not make the bucket public as a workaround. Follow the approved quarantine and retention procedure for sensitive uploads.

## Key compromise response
1. Revoke the affected managed key immediately.
2. Create a replacement in the same environment with minimum scopes.
3. Update the client secret store and verify with a non-sensitive request.
4. Review security events, audit events, and request IDs.
5. Preserve the event trail and notify the service owner without including the compromised secret.
6. If a legacy shared key was exposed, rotate it for all dependent clients.

## Database migration and rollback
- Never apply production migrations automatically at startup.
- Back up and test forward migration and restore on a non-production copy first.
- Prefer forward repair for additive changes; destructive rollback may lose new data.
- If schema and app versions disagree, pause ingestion and reconcile before processing more jobs.
- Production migration execution requires explicit approval.

## Provider integrations
An unavailable, manual-review, or not-found result must never be converted into verified by fallback logic. Before enabling BRS, KRA, IPRS, or another provider, confirm the API contract, credentials, permitted purpose, processing terms, rate limits, timeout budget, retry policy, and audit requirements. Imported data and fuzzy name matches remain review evidence, not legal certification.

## External release blockers
Repository changes alone cannot apply reviewed production migrations, configure Render settings, confirm provider credentials/contracts, configure hosted alerts/backups, run a real staging import, or approve privacy and data-processing policies. These require an authorized operator and/or provider.
