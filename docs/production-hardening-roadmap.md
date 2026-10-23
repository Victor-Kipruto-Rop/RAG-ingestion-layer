# Production Hardening Roadmap

This roadmap is the release checklist for taking PesaGuard Registry Datasource from prototype to production-grade infrastructure. Deliver changes as reviewable pull requests; keep production data and secrets unchanged unless an explicitly approved migration or deployment is underway.

## Phase 1 — Baseline and CI stabilization
- [ ] Re-run CI and resolve the first failing step from its logs; the earlier run's log artifacts were unavailable, so the original failure cause is not yet confirmed. CI steps are now explicitly named to make fresh failures actionable.
- [x] Verify the streaming CSV parser and add a regression test that exercises a multi-thousand-row fixture through the file iterator.
- [ ] Record test results from a fresh successful CI run and complete a read-only production health check. Render service configuration was inspected without mutation; its health-check path is currently unset.
- [ ] Keep streaming work isolated until CI passes; do not merge or deploy as part of baseline verification.

## Phase 2 — Database migrations and warehouse integrity
- [ ] Add Alembic as the schema-change entry point.
- [ ] Reconcile Alembic with existing SQL migration history before stamping any deployed database.
- [ ] Test clean-database bootstrap and existing-schema upgrade paths.
- [ ] Tune connection pools for the actual Render/Supabase connection mode.
- [ ] Review unique identifier indexes and add supported text-search indexes only after duplicate/data checks.

## Phase 3 — Streaming ingestion and dead-letter isolation
- [x] Stream CSV records through disk-backed spooling and bound PDF diagnostics.
- [x] Persist sanitized dead-letter records with source job, row number, safe error category and restricted diagnostics.
- [x] Commit CSV rows in batches and persist row progress for resumable processing.
- [x] Preserve bounded PDF/OCR behavior and manual-review status.
- [x] Add per-job inspection, retry from committed checkpoints, paginated DLQ inspection, and streamed spreadsheet-safe error CSV exports.
- [ ] Add integration tests for transient storage/database failures, stale-job recovery, and direct-upload integrity against the actual target database/storage stack.

## Phase 4 — Entity resolution
- [ ] Normalize legal suffixes and names.
- [ ] Generate fuzzy candidates with RapidFuzz or pg_trgm.
- [ ] Never auto-merge on name similarity alone; preserve match evidence and review state.
- [ ] Test conflicting identifiers and false-positive cases.

## Phase 5 — Security and compliance
- [ ] Validate production environment settings at startup without printing secret values.
- [ ] Add HMAC request signing, timestamp tolerance, nonce/replay protection and key rotation.
- [ ] Redact PII and credentials from raw payloads, logs and error messages.
- [ ] Test authentication, tenant boundaries and failure modes.

## Phase 6 — API resilience and cache policy
- [ ] Add timeouts, bounded exponential backoff with jitter and circuit breakers for configured providers.
- [ ] Add Redis token-bucket rate limiting with an explicit Redis-outage policy.
- [ ] Add cache TTL/invalidation and freshness metadata.
- [ ] Test provider outage, timeout, retry storm and stale-cache scenarios.

## Phase 7 — Observability
- [ ] Emit structured JSON logs with request and job correlation IDs.
- [ ] Expose Prometheus metrics for HTTP, DB, queue, ingestion throughput and cache.
- [ ] Use histograms for p95/p99 latency; do not claim an SLA without load-test evidence.
- [ ] Add health checks, alerts and operational runbooks.

## Phase 8 — Dashboard readiness
- [ ] Add React error boundaries and truthful upload/processing states.
- [ ] Add server pagination/filtering and virtualize large tables when measured volume warrants it.
- [ ] Add frontend tests for error, empty, loading and large-result states.

## Phase 9 — Containers and CI/CD
- [ ] Use multi-stage non-root API, worker and frontend images.
- [ ] Require pytest, focused Ruff checks, frontend tests/build, and container builds on PRs.
- [ ] Add dependency/container scanning and secret scanning.
- [ ] Deploy only after checks and migration review; document rollback.

## Phase 10 — End-to-end sign-off
- [ ] Test large files, malformed rows, retries, duplicate submissions, stale jobs and provider outages.
- [ ] Test backup/restore and migration recovery strategy.
- [ ] Verify production health and permissions without exposing secrets.
- [ ] Run the final Windows Docker Compose workflow with fictional sample data.
- [ ] Record unmet objectives and obtain explicit release approval.

## Non-negotiable safety rules
- Never paste secrets into chat or commit them.
- Never run destructive SQL or process queued production jobs as a test.
- Never stamp an existing database until its schema has been compared to the baseline.
- Fuzzy name matches are review candidates, not proof of identity.
- CI checks must pass; do not mask failures with continue-on-error.