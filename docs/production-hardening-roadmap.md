# PesaGuard Datasource — Phased Hardening and Release Status

Status is separated into **implemented in source**, **verified by CI**, and **requires operational approval**. A source checkbox is not evidence of a successful deployment, an external provider connection, or production migration.

## Phase 1 — Baseline and CI stabilization
- [x] Streaming CSV parsing and bounded-row regression coverage exist.
- [x] CI has named backend compilation, Ruff, pytest, Alembic smoke, frontend, and container-build steps.
- [x] Tests cover PII masking, worker stale-job recovery, HMAC replay protection, and CSV parsing.
- [ ] Obtain a successful CI run for the final hardening branch and fix every failure.
- [ ] Perform and record a read-only production health check; do not process queued production jobs as a test.

## Phase 2 — Database migrations and warehouse integrity
- [x] Alembic is configured for backend schema changes and revisions 0001–0004 are forward-only.
- [x] Revision 0005 creates environment-scoped API key and audit tables for Alembic-managed fresh installations.
- [x] SQL migration 009 is kept as the corresponding SQL/Supabase migration path and enables RLS on key/audit tables.
- [x] Production configuration requires an explicit `API_ENVIRONMENT=production`; the safe application default is sandbox.
- [ ] Reconcile the actual target database with both migration histories before stamping or applying anything.
- [ ] Validate upgrade of a restored schema snapshot and review production-like query plans/index usage.
- [ ] Obtain explicit approval and backup evidence before applying production migrations.

## Phase 3 — Streaming ingestion and dead-letter isolation
- [x] CSV processing uses disk-backed streaming, row limits, bounded batches, and persisted row progress.
- [x] Failed-row dead-letter storage keeps row context with PII-sensitive fields redacted.
- [x] Stale-job recovery, retry metadata, correlation IDs, and bounded PDF/OCR manual-review states are present.
- [ ] Complete integration tests for partial-batch commit, duplicate submissions, retry/resume, malformed rows, and stale leases against a disposable database.
- [ ] Benchmark representative fictional files against memory and runtime limits.
- [ ] Confirm private-object retention and deletion controls in the storage account.

## Phase 4 — Data quality and entity resolution
- [x] Registry search, quality indicators, source freshness, and candidate matching are available.
- [x] Entity matching normalizes legal suffixes and uses fuzzy similarity as a review aid only.
- [x] Personal identifiers are excluded from the general registry payload by the normalizer.
- [ ] Add conflict-focused tests for duplicate identifiers, changed source values, and false-positive matches.
- [ ] Build durable reviewer decisions and change-lineage UI before any merge automation.
- [ ] Verify quality metrics against a known fictional fixture with expected counts.

## Phase 5 — API key security and compliance
- [x] Customer API keys are scoped to an organization and either sandbox or production.
- [x] Key secrets are generated randomly, hashed at rest, revealed once, and support expiry, rotation, and revocation.
- [x] Production key creation requires verified-organization and owner/admin claims.
- [x] Runtime authentication rejects wrong-environment keys and insufficient scopes; these attempts are audited without persisting raw secrets.
- [x] JWT parsing now bounds token size, checks HS256 signature/expiry/not-before/issuer/audience, and rejects malformed claims.
- [x] Key and audit tables have PostgreSQL RLS enabled by the migration.
- [ ] Validate that the actual PesaGuard identity issuer emits the documented claims and uses the configured issuer/audience/signing secret.
- [ ] Coordinate migration from legacy shared `REGISTRY_API_KEYS`; legacy shared keys do not have per-key environment isolation.
- [ ] Complete privacy, retention, and role-policy review before accepting confidential customer datasets.

## Phase 6 — API resilience and cache policy
- [x] Registry lookups have cache-aside TTLs, negative caching, and post-import invalidation hooks.
- [x] Lookup rate limiting supports a Redis-backed shared token bucket with an explicit production failure policy.
- [x] Bounded transient retry and circuit-breaker helpers are implemented and unit-tested.
- [ ] Add end-to-end tests for Redis outage, stale-cache invalidation after import, timeout, and retry budget behavior.
- [ ] Add provider-specific circuit-breaker settings only after provider contracts and timeouts are known.

## Phase 7 — Observability and operations
- [x] Structured request logs include correlation IDs and route-level latency.
- [x] Protected Prometheus metrics include HTTP/DB timings and ingestion queue/progress metrics.
- [x] Liveness, readiness, and basic health endpoints are present.
- [x] Release, key-compromise, ingestion-recovery, backup/restore, and external-provider gates are documented.
- [ ] Configure alert rules and dashboards in the actual monitoring platform.
- [ ] Verify Render health-check configuration and readiness after an approved staging release.
- [ ] Run a measured load test before setting latency/availability SLOs.

## Phase 8 — Dashboard readiness
- [x] Responsive dashboard, API key management, quality and source freshness views exist.
- [x] React error boundary is wired into the application entry point.
- [x] API-key UI keeps the user access token in session storage, reveals new secrets once, and uses explicit confirmation for destructive actions.
- [x] Added API-key component tests for authentication feedback, token storage behavior, and one-time secret reveal.
- [ ] Run frontend tests/build on the final branch and fix any failures.
- [ ] Verify pagination/filtering behavior at realistic record volume and perform accessibility/mobile review.

## Phase 9 — Containers and CI/CD
- [x] API, worker, and frontend use multi-stage container builds and non-root runtime users.
- [x] CI compiles, lints, tests, runs an Alembic SQLite smoke test, and builds API/worker/frontend containers.
- [x] Added CodeQL, secret scanning, dependency-review, and weekly Dependabot update proposals.
- [ ] Confirm all new security workflows pass and review findings instead of suppressing them.
- [ ] Add a lockfile-based frontend install and a documented image/SBOM/dependency-vulnerability policy.
- [ ] Confirm branch protection requires the selected checks; repository branch protection is not changed by this code PR.

## Phase 10 — End-to-end sign-off and external integrations
- [x] Added explicit release gates for fictional upload-to-lookup tests, key-environment checks, and recovery operations.
- [x] Documented that imported records and OCR output are not authoritative business verification.
- [ ] Run upload → worker → warehouse → lookup end-to-end on a disposable environment using fictional fixtures.
- [ ] Test backup restore and migration recovery on a disposable database and private object-storage copy.
- [ ] Integrate BRS/KRA/IPRS/commercial providers only after credentials, permitted purpose, contract, response schema, rate limits, and data-processing terms are approved.
- [ ] Perform read-only production health verification and obtain explicit release approval before merge/deploy or production migration.

## Release safety rules
- Never commit API keys, JWT signing secrets, database URLs, or confidential registry data.
- Never run migrations against a live database merely to satisfy CI; do not mix the SQL and Alembic migration paths on the same database.
- Never run queued production jobs as a smoke test or claim a provider is connected without evidence.
- Sandbox and production require separate deployments, databases, storage, credentials, and explicit server-side `API_ENVIRONMENT` values.
- Name similarity, imported registry data, and extracted PDF text are evidence for review—not proof of identity or legal verification.
