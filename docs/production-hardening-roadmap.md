# PesaGuard Datasource — implementation and release roadmap

This document distinguishes code present in the repository from work that still requires verification, credentials, migration approval, or deployment. Code in a branch is not considered production-ready until tests pass and release checks are completed.

## Phase 1 — Baseline and CI stabilization
- [x] Streaming CSV parser and large-fixture regression coverage are present.
- [x] Named CI steps are configured to make failures actionable.
- [x] Managed API-key hardening regression tests added for environment mismatch, scope denial, key hashing, and operator authentication.
- [x] Added route-level regression tests for key creation, hash-only persistence, environment mismatch security events, scope denial, revocation, rotation and review-only quality matches. CI execution is still pending verification.
- [ ] Run the full backend test suite and frontend build/tests on the latest commit; record results.
- [ ] Inspect the first failing CI job if CI fails, and fix it rather than suppressing it.
- [ ] Complete a read-only production health check; do not process or alter queued production jobs as a test.
- [ ] Confirm the Render health-check path and production configuration with a release owner.

## Phase 2 — Database migrations and warehouse integrity
- [x] Additive SQL migrations exist for managed API keys/security events and ingestion schema changes.
- [x] Production startup avoids automatic table creation.
- [ ] Reconcile the SQL migration sequence with Alembic before making Alembic the single schema-change entry point.
- [ ] Test both clean database bootstrap and upgrade of a schema snapshot matching the deployed database.
- [ ] Review indexes against query plans and actual data volume.
- [ ] Apply migrations only after explicit approval and a backup/rollback plan; never run them automatically from this branch.

## Phase 3 — Ingestion reliability
- [x] CSV processing uses disk-backed/bounded processing and persisted progress for retry/resume.
- [x] Failed-row/dead-letter storage and safe diagnostics are present.
- [x] Retry/lease and correlation-ID migrations are present.
- [x] PDF/OCR work is bounded and does not imply authoritative verification.
- [ ] Verify partial-batch commit, idempotency, duplicate submissions, retry and stale-lease behavior with automated integration tests.
- [ ] Validate max-size handling with representative files without using confidential production documents.
- [ ] Confirm object retention, quarantine and deletion procedures for R2.

## Phase 4 — Data quality and entity resolution
- [x] Quality summary, source freshness, validation-rule descriptions and fuzzy match candidates are exposed.
- [x] Match candidates are explicitly review-only; name similarity never triggers automatic merges.
- [x] Added a regression test for quality summary output and review-only fuzzy match candidates.
- [ ] Add tests for conflicting identifiers, repeated imports, false positives and freshness boundaries.
- [ ] Add a durable reviewer decision workflow before any future merge/identity-resolution automation.
- [ ] Add lineage/change-history UI and verify source attribution end to end.

## Phase 5 — API key security and compliance
- [x] Managed keys use random secrets, one-way SHA-256 digests at rest, one-time reveal, expiry, rotation and revocation.
- [x] Sandbox/production keys are checked against the server-configured deployment environment.
- [x] Wrong-environment and insufficient-scope requests return explicit errors and attempt to record security events.
- [x] The key prefix is checked against the environment stored for the key.
- [x] Key management requires a server-side operator bearer token; it is not tenant self-service authentication.
- [x] HMAC signing, timestamp tolerance, nonce replay protection and Redis-backed shared rate limiting are implemented as optional controls.
- [x] Added API-level regression tests for key creation, rotation, revocation, scope denial and environment mismatch. CI execution and isolated migration-backed PostgreSQL verification remain pending.
- [ ] Coordinate the migration from legacy shared REGISTRY_API_KEYS; legacy shared keys do not have per-key environment isolation.
- [ ] Keep DATASOURCE_ADMIN_TOKEN, HMAC secrets, Redis credentials and production API keys server-side only.
- [ ] Review data retention, privacy and access-control policy with the service owner before storing real registry datasets.

## Phase 6 — API resilience and cache policy
- [x] Lookup rate limiting, Redis-backed token bucket, cache TTLs and cache-aside behavior are implemented.
- [x] Source freshness metadata is exposed.
- [ ] Add integration tests for Redis outage, stale cache, invalidation after import, timeout and retry behavior.
- [ ] Define operational retry budgets and circuit breakers for each future external provider adapter; do not simulate providers as if they were connected.
- [ ] Document the chosen fail-open/fail-closed policy for each optional dependency and validate it in staging.

## Phase 7 — Observability and operations
- [x] Structured request logs include correlation IDs and request timing.
- [x] Prometheus HTTP/DB/ingestion metrics and protected /metrics endpoint are present.
- [x] Liveness, readiness and health endpoints are present.
- [ ] Configure alerts and dashboards in the actual monitoring platform.
- [ ] Set the Render health-check path and verify readiness after a controlled release.
- [ ] Document incident response, key compromise, queue recovery, restore and rollback runbooks.
- [ ] Measure latency/throughput under load before making SLO/SLA claims.

## Phase 8 — Dashboard readiness
- [x] Responsive dashboard, API-key management, quality views, source freshness, job/record views and status messaging are present in the feature branch.
- [x] API-key screen does not persist the operator token to local storage and reveals a new secret only once.
- [ ] Add frontend tests for loading, empty, failed API, expired token, copy failure and narrow mobile layout.
- [ ] Add a React error boundary and accessible confirmation/notification handling.
- [ ] Verify server pagination/filtering for high-volume record and audit-log tables.
- [ ] Confirm frontend build-time VITE_API_BASE_URL is set for each deployment and no server secret enters the browser bundle.

## Phase 9 — Containers and CI/CD
- [ ] Require backend tests, focused linting, frontend tests/build and container builds on pull requests.
- [ ] Add dependency, container and secret scanning; fix findings rather than bypassing checks.
- [ ] Verify non-root runtime, health checks, pinned build inputs and image-size limits for API, worker and frontend.
- [ ] Document a staged rollout and rollback plan for schema and service changes.

## Phase 10 — Integrations and end-to-end release sign-off
- [ ] Build provider adapters only after credentials, contracts, allowed purpose, rate limits and data-processing terms are confirmed.
- [ ] Test complete CSV/PDF upload → queued job → worker → warehouse → lookup/dashboard flow with fictional fixtures.
- [ ] Verify backup/restore and migration recovery using a non-production database.
- [ ] Complete security, privacy and operational review; record unresolved risks.
- [ ] Obtain explicit release approval before merging/deploying or applying production migrations.

## Scope and safety notes
- Datasource registry imports are not proof that an organization is verified by BRS, KRA, IPRS or another authority.
- The current key manager is operator-token protected; proper customer/tenant self-service keys require a verified user identity and organization-membership/role model. Do not present the operator token as tenant authentication.
- A production deployment must set DATASOURCE_ENVIRONMENT=production; sandbox must set DATASOURCE_ENVIRONMENT=sandbox. The request header cannot choose the environment.
- Production migrations and deployment changes are deliberately manual and require approval.
- Never commit credentials or confidential datasets. Never claim a test, deployment, integration or verification succeeded without evidence.
