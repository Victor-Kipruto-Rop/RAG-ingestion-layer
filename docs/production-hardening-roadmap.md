# PesaGuard Datasource — implementation and release roadmap

This roadmap distinguishes repository code from checks that still require execution, real deployment configuration, authorized credentials, or explicit release approval. A merged change is not evidence that production behavior has been verified.

## Phase 1 — Baseline and CI stabilization

- [x] Bounded-memory CSV parser and row-limit regression tests are present.
- [x] CI compiles backend modules, runs backend tests, checks selected Ruff rules, smoke-tests Alembic on disposable SQLite, and builds service containers.
- [x] Frontend test command is now part of CI; dashboard error-boundary regression test added.
- [ ] Verify CI is green for the current pull request and fix failures rather than skipping them.
- [ ] Perform a read-only production health check and record the result; do not process production jobs as a test.

## Phase 2 — Database migrations and warehouse integrity

- [x] Additive SQL migrations and Alembic configuration are present.
- [x] Added a migration-safety guide documenting the two migration histories and prohibiting blind stamping or double application.
- [ ] Reconcile SQL migration files with Alembic revisions and choose one canonical forward path.
- [ ] Test a clean bootstrap and upgrade from a production-like PostgreSQL schema snapshot.
- [ ] Review index plans, connection pooling, and duplicate constraints against actual database state.
- [ ] Apply production migrations only after explicit approval, backup, and rollback planning.

## Phase 3 — Ingestion reliability

- [x] CSV parser supports row-by-row iteration and bounded record limits.
- [x] Durable ingestion jobs, idempotency metadata, retries/leases, row progress, sanitized row-error/dead-letter handling, and correlation IDs exist in the codebase.
- [x] PDF processing is bounded and does not imply authoritative verification when extraction is unavailable.
- [ ] Run integration tests for partial batches, duplicate uploads, retry/resume, stale leases, and object-storage failures.
- [ ] Validate maximum-size fixtures and R2 retention/quarantine/deletion procedures without confidential production files.

## Phase 4 — Data quality and entity resolution

- [x] Name normalization and fuzzy match candidates are available.
- [x] Similarity results are candidates for human review only; name similarity must never auto-merge entities.
- [x] Source provenance, record versions, quality summary, and source-freshness concepts are present.
- [ ] Expand regression coverage for conflicting identifiers, repeated imports, false positives, stale-source boundaries, and lineage.
- [ ] Implement a durable reviewer decision workflow before any automated identity-resolution action.

## Phase 5 — API security and compliance

- [x] Environment-scoped API keys, key hashing, one-time reveal, expiry, rotation, revocation, scopes, and organization-aware key management are implemented in code.
- [x] Key-management routes validate signed PesaGuard user tokens and organization role claims; production issuer/audience configuration is required.
- [x] HMAC request signing, timestamp validation, nonce replay protection, and optional Redis-backed shared rate limiting are implemented.
- [x] Environment mismatch and insufficient-scope errors are explicit; raw API secrets must not be persisted in security events.
- [ ] Run tenant-isolation and key lifecycle integration tests against a disposable PostgreSQL database.
- [ ] Configure and verify production JWT issuer/audience/signing secret with the trusted identity service.
- [ ] Coordinate the migration from legacy shared API keys; legacy keys do not provide per-key environment isolation.
- [ ] Review privacy, lawful data use, retention, and access policy with the service owner.

## Phase 6 — API resilience and cache policy

- [x] Redis-backed token-bucket rate limiting, lookup cache TTLs, cache invalidation helpers, and provider retry/circuit-breaker utilities exist.
- [x] Source freshness metadata is represented in the API.
- [ ] Test Redis outage policy, stale cache, cache invalidation, provider timeout, bounded retries, and circuit recovery.
- [ ] Configure Redis in the target environment and verify distributed behavior across more than one API instance.
- [ ] Build external provider adapters only after contracts, permissions, credentials, rate limits, and failure semantics are approved.

## Phase 7 — Observability and operations

- [x] Structured request logs, correlation IDs, HTTP/database/ingestion metrics, and health endpoints exist.
- [x] Added a release and incident runbook covering key compromise, ingestion backlog, bad imports, migration checks, and recovery.
- [ ] Configure actual monitoring dashboards and alert rules in the deployment platform.
- [ ] Verify health-check path and alert delivery in the deployed environment.
- [ ] Conduct a load test before making latency or availability SLO/SLA claims.
- [ ] Test backup restoration and object-store recovery.

## Phase 8 — Dashboard readiness

- [x] Responsive dashboard, API-key management view, and explicit API error messaging exist.
- [x] A React error boundary provides a recoverable fallback without logging user props or credentials.
- [x] Added a component regression test for the error-boundary fallback and included frontend tests in CI.
- [ ] Verify the complete frontend test/build result in CI.
- [ ] Add remaining component coverage for loading/empty/error states, expired tokens, clipboard failures, and narrow mobile layouts.
- [ ] Verify server-side pagination/filtering for all high-volume lists.
- [ ] Confirm deployment-time API URL and ensure no server-only secret is included in the browser bundle.

## Phase 9 — Containers and CI/CD

- [x] CI builds API, worker, and frontend containers.
- [x] Added Dependabot update configuration for Python, npm, Docker images, and GitHub Actions.
- [x] Added scheduled/pull-request secret scanning and Python/frontend dependency audit jobs.
- [ ] Verify new security workflow results and remediate all high/critical findings.
- [ ] Review non-root runtime, health checks, pinned build inputs, and image size for all containers.
- [ ] Configure branch protection to require the intended CI and security checks; this requires repository settings access.
- [ ] Test staged rollout and rollback in a non-production environment.

## Phase 10 — Integrations and end-to-end release sign-off

- [ ] Run end-to-end tests for large files, malformed rows, retries, duplicate submissions, stale jobs, and provider outages.
- [ ] Complete PostgreSQL migration upgrade and restore testing.
- [ ] Verify production health, permissions, environment separation, and monitoring without exposing secrets.
- [ ] Run the Windows Docker Compose workflow with fictional sample data.
- [ ] Connect and validate approved BRS/KRA or other provider credentials; no provider should be represented as live until verified.
- [ ] Record unresolved risks and obtain explicit release approval before deployment.

## Release blockers outside a code-only change

The following cannot be honestly marked complete from a repository change alone: applying production migrations, changing Render/Supabase/R2 secrets, verifying live production health, enabling real government/vendor integrations, configuring monitoring and branch-protection settings, restoring a production backup, and approving a deployment.

## Safety rules

- Never paste credentials into chat, logs, frontend build variables, or source control.
- Never test by altering production data or processing confidential production documents.
- Never present imported registry data or fuzzy matches as authoritative company verification.
- Never claim a test, integration, migration, deployment, or production check passed without recorded evidence.
