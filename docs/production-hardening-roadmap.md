# Production Hardening Roadmap

This is a status-based release checklist for PesaGuard Registry Datasource. It distinguishes repository implementation from deployment validation. A checked item means the corresponding capability is present in source; it does not imply production rollout or successful CI unless explicitly stated.

## Phase 1 — Baseline and CI stabilization
- [x] Add streaming CSV parser regression coverage for a multi-thousand-row fixture.
- [x] Name CI steps for backend compilation/lint/tests, migration smoke test, frontend build, and container builds.
- [ ] Obtain a fresh successful CI run. The latest observed run (workflow run 39948456818) failed in both jobs, but job logs were unavailable through the connector, so the first failing step is not confirmed.
- [ ] Perform a read-only production health check and record evidence. No production health check is claimed by this PR.
- [ ] Merge/deploy only after CI is green and the schema change is reviewed.

## Phase 2 — Database migrations and warehouse integrity
- [x] Keep additive SQL migrations under `database/migrations/`; Alembic is configured for the backend.
- [x] Add the managed API-key and security-event schema in migration `009_managed_api_keys.sql`, with indexes and Supabase RLS enabled.
- [ ] Reconcile Alembic revision history with the hand-maintained SQL migration history before stamping any existing database.
- [ ] Validate clean bootstrap and existing-schema upgrade against disposable databases and the exact target schema.
- [ ] Tune connection pools for the deployed Render/Supabase connection mode and review query plans/indexes using production-like data.
- [ ] Apply migration 009 only after database backup, review, and explicit deployment approval.

## Phase 3 — Streaming ingestion and dead-letter isolation
- [x] Use a disk-backed CSV parser and bounded database batches with persisted row progress.
- [x] Persist sanitized row-level failures in a dead-letter table; retain job and row references.
- [x] Support idempotency keys, bounded retries, stale-job recovery, and row-level error inspection.
- [x] Keep PDF processing bounded and report unsupported extraction as a manual/needs-processing state rather than fabricating extracted data.
- [ ] Run a large-file benchmark and retry/rollback tests against disposable PostgreSQL, not production data.

## Phase 4 — Entity resolution
- [x] Normalize legal names and identifiers and provide fuzzy candidate matching.
- [x] Keep name similarity as a review aid; do not auto-merge organizations based on a fuzzy score.
- [x] Return source and provenance information for review.
- [ ] Expand tests for conflicting identifiers, common-name collisions, and multilingual/legal-suffix false positives.
- [ ] Persist human adjudication decisions and evidence if entity-resolution decisions become part of a regulated workflow.

## Phase 5 — Security and compliance
- [x] Validate required production configuration at startup without printing secret values.
- [x] Support HMAC signatures, timestamp tolerance, nonce/replay protection, and optional Redis-backed distributed replay protection.
- [x] Hash managed API-key secrets, support expiry/rotation/revocation/scopes, and audit security events.
- [x] Enforce server-configured environment boundaries; sandbox keys are rejected in production and misuse is recorded when the database is available.
- [x] Fail closed when a managed-looking key is presented while managed-key support is disabled; it cannot fall back to the legacy shared-key allowlist.
- [x] Keep the operator token in page memory only and never persist it in browser local storage.
- [ ] Replace the single operator token with a real identity provider, role-based authorization, organization membership checks, and tenant-scoped key administration before offering customer self-service.
- [ ] Complete a PII/data-retention review and a security review of production logs and raw imported payloads.
- [ ] Migrate all legacy shared-key callers to managed keys before retiring `REGISTRY_API_KEYS`; legacy keys are not individually environment-scoped.

## Phase 6 — API resilience and cache policy
- [x] Implement Redis token-bucket rate limiting with a defined production Redis-outage behavior.
- [x] Add bounded retry/circuit-breaker helpers for transient provider calls.
- [x] Implement cache TTLs and negative-cache TTLs for registry lookups.
- [x] Expose source freshness state from actual import timestamps and configured freshness SLAs.
- [ ] Add provider-specific outage/timeout/retry-storm tests once real provider adapters and credentials are approved.
- [ ] Confirm Redis is configured on every production replica before treating rate limiting/replay prevention as distributed guarantees.

## Phase 7 — Observability
- [x] Emit structured JSON request logs with correlation IDs and response timings.
- [x] Expose Prometheus counters/histograms and ingestion/queue gauges behind a metrics token.
- [x] Expose live/readiness/health endpoints and warehouse access telemetry.
- [ ] Configure production alert rules and on-call/runbook ownership in the monitoring platform.
- [ ] Collect load-test evidence before publishing latency or availability SLOs.

## Phase 8 — Dashboard readiness
- [x] Add an application error boundary and honest loading/error/empty states.
- [x] Add server-side organization pagination/search and operational pages for ingestion, data quality, sources, audit logs, and API keys.
- [x] Avoid fake metrics and label unavailable integrations as not configured.
- [x] Add focused API-client tests for successful responses, structured API errors, and multipart upload headers.
- [ ] Add broader component/UI tests for keyboard accessibility and large result sets.
- [ ] Add table virtualization only after measured record volumes justify it.

## Phase 9 — Containers and CI/CD
- [x] Build API, worker, and frontend containers in CI.
- [x] Run backend tests, focused Ruff checks, Alembic smoke test, and frontend production build in CI.
- [ ] Confirm each Dockerfile uses a non-root runtime and minimal production image; resolve any container hardening gaps found by review.
- [ ] Add dependency, container-image, and secret scanning to CI.
- [ ] Make successful CI a required branch-protection check and document deploy rollback steps.
- [ ] Re-run the pipeline and resolve its actual failure before merge; current workflow evidence is a failed run with unavailable logs.

## Phase 10 — End-to-end sign-off
- [ ] Test large files, malformed rows, retry/resume, duplicate submissions, stale jobs, and Redis/provider outages in an isolated environment.
- [ ] Test backup/restore and migration recovery.
- [ ] Verify production health, service permissions, CORS, TLS, and secret configuration without revealing credentials.
- [ ] Run the Windows Docker Compose workflow with fictional sample data and capture the results.
- [ ] Complete approved BRS/KRA/commercial provider onboarding and integration tests. No live external registry connection is claimed until access is authorized and configured.
- [ ] Record residual risks and obtain explicit release approval.

## Non-negotiable safety rules
- Never paste secrets into chat or commit them.
- Never run destructive SQL or process queued production jobs as a test.
- Never stamp an existing database until its schema has been compared to the baseline.
- Fuzzy name matches are review candidates, not proof of identity.
- Never mark CI green without an observed successful run.
- Do not expose operator-only key administration as tenant self-service without a real identity and tenant authorization layer.
