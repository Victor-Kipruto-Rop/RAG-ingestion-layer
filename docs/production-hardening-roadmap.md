# Production Hardening Roadmap

This roadmap is the release checklist for taking PesaGuard Registry Datasource from prototype to production-grade infrastructure. Deliver changes as reviewable pull requests; keep production data and secrets unchanged unless an explicitly approved migration or deployment is underway.

## Phase 1 — Baseline and CI stabilization
- [ ] Diagnose failing CI from actionable step logs; do not suppress failing checks.
- [ ] Verify streaming CSV parsing and add regression tests.
- [ ] Record baseline test results and current production health without mutating data.
- [ ] Keep streaming work in draft PR #14 until CI passes.

## Phase 2 — Database migrations and warehouse integrity
- [ ] Add Alembic as the schema-change entry point.
- [ ] Reconcile Alembic with existing SQL migration history before stamping any deployed database.
- [ ] Test clean-database bootstrap and existing-schema upgrade paths.
- [ ] Tune connection pools for the actual Render/Supabase connection mode.
- [ ] Review unique identifier indexes and add supported text-search indexes only after duplicate/data checks.

## Phase 3 — Streaming ingestion and dead-letter isolation
- [ ] Stream CSV records and bounded PDF data without whole-file RAM loading.
- [ ] Add durable dead-letter records with source job, row number, safe error category and restricted diagnostics.
- [ ] Ensure a bad row does not roll back valid rows; add transaction batching and idempotency tests.
- [ ] Preserve bounded PDF/OCR behavior and manual-review status.

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
- [x] Add durable quality-review cases and append-only decisions with audit logging; decisions do not automatically merge or rewrite organization records.
- [x] Add dashboard review queue for creating cases, collecting reviewer notes, and recording review decisions against the real API.
- [ ] Run the new review workflow tests and full CI on the latest commit before marking this phase verified.
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