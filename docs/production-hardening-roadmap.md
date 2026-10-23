# Production Hardening Roadmap

This roadmap is the release checklist for taking PesaGuard Registry Datasource from prototype to production-grade infrastructure. Deliver changes as reviewable pull requests; keep production data and secrets unchanged unless an explicitly approved migration or deployment is underway.

## Phase 1 — Baseline and CI stabilization
- [ ] Re-run CI and resolve the first failing step from its logs; the earlier run's log artifacts were unavailable, so the original failure cause is not yet confirmed. CI steps are now explicitly named to make fresh failures actionable.
- [x] Verify the streaming CSV parser and add a regression test that exercises a multi-thousand-row fixture through the file iterator.
- [ ] Record test results from a fresh successful CI run and complete a read-only production health check. Render service configuration was inspected without mutation; its health-check path is currently unset.
- [ ] Keep streaming work isolated until CI passes; do not merge or deploy as part of baseline verification.

The managed-key migration and regression tests in this branch are implementation work only; CI must pass before this phase is considered complete.

## Phase 2 — Database migrations and warehouse integrity
- [x] Add Alembic as the schema-change entry point; managed API-key tables now have a forward-only Alembic revision.
- [ ] Reconcile Alembic with existing SQL migration history before stamping any deployed database.
- [x] Test clean-database bootstrap includes the managed API-key tables on disposable SQLite.
- [ ] Test an existing-schema upgrade against a restored staging copy.
- [ ] Tune connection pools for the actual Render/Supabase connection mode.
- [ ] Review unique identifier indexes and add supported text-search indexes only after duplicate/data checks.

## Phase 3 — Streaming ingestion and dead-letter isolation
- [x] Stream CSV records with bounded database batches; bound PDF diagnostics and keep PDF extraction manual-review-only.
- [x] Add durable dead-letter records with source job, row number, safe error category and restricted diagnostics.
- [x] Commit ingestion in bounded batches, persist row progress and support idempotency; keep expanding failure/retry coverage.
- [x] Preserve bounded PDF/OCR behavior and manual-review status.

## Phase 4 — Entity resolution
- [x] Normalize legal names and identifiers.
- [x] Generate fuzzy candidates with RapidFuzz and PostgreSQL trigram search where available.
- [x] Keep similarity matches as review candidates; do not auto-merge on name similarity alone.
- [x] Test conflicting registration/PIN identifiers and false-positive name candidates; conflicts go to the dead-letter/manual-review path.

## Phase 5 — Security and compliance
- [x] Validate production environment settings at startup without printing secret values.
- [x] Add optional HMAC signing, timestamp tolerance, nonce/replay protection, and managed API-key rotation/revocation.
- [x] Redact sensitive fields from dead-letter diagnostics and avoid logging raw API key values.
- [x] Add regression coverage for HMAC, managed-key environment isolation, scopes, revocation and expiry. Tenant-level auth is not exposed by this internal registry service; add it before offering customer-managed keys.

## Phase 6 — API resilience and cache policy
- [x] Add bounded retry/backoff and circuit-breaker helpers for transient provider failures.
- [x] Add Redis-backed token-bucket limiting with a documented per-process fallback caveat and production fail-closed behavior when configured Redis is unavailable.
- [x] Add cache TTL/invalidation and source-freshness metadata.
- [x] Test transient timeouts, bounded retries, circuit-breaker recovery, cache TTL/invalidation and Redis outage fallback.

## Phase 7 — Observability
- [x] Emit structured JSON logs with request and job correlation IDs.
- [x] Expose Prometheus metrics for HTTP, DB, queue, ingestion throughput and cache.
- [x] Use request and database histograms for latency distribution; do not claim an SLA without load-test evidence.
- [x] Add health endpoints and an operations runbook; production alert rules still need to be configured in the selected monitoring platform.

## Phase 8 — Dashboard readiness
- [x] Add a React error boundary and keep upload/processing labels tied to API responses.
- [x] Use server pagination for organization and ingestion-job data. Virtualize only if production volume measurements justify it.
- [x] Add frontend regression tests for the error boundary and API client; expand with page-level loading/empty/large-result tests.

## Phase 9 — Containers and CI/CD
- [x] Use multi-stage, non-root API, worker and frontend images.
- [x] Require pytest, focused Ruff checks, frontend tests/build, and container builds on PRs.
- [x] Add CodeQL analysis for Python and JavaScript/TypeScript plus weekly Dependabot update proposals.
- [ ] Enable and verify repository secret scanning/push protection in GitHub settings; a workflow file cannot turn on account-level settings.
- [ ] Deploy only after checks and migration review; document rollback.

## Phase 10 — End-to-end sign-off
- [ ] Complete end-to-end large-file, malformed-row, retry, duplicate-submission, stale-job and provider-outage tests across a full disposable stack.
- [ ] Test backup/restore and migration recovery strategy.
- [ ] Verify production health and permissions without exposing secrets; this requires an approved read-only production check.
- [ ] Run the final Windows Docker Compose workflow with fictional sample data.
- [ ] Record unmet objectives and obtain explicit release approval.

## Non-negotiable safety rules
- Never paste secrets into chat or commit them.
- Never run destructive SQL or process queued production jobs as a test.
- Never stamp an existing database until its schema has been compared to the baseline.
- Fuzzy name matches are review candidates, not proof of identity.
- CI checks must pass; do not mask failures with continue-on-error.