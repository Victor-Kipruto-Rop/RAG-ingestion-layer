# PesaGuard Datasource — Implementation Phases

This plan defines deliverables and release gates. It is intentionally honest about features requiring external credentials, provider contracts, or a real tenant identity system.

## Phase 1 — API key lifecycle and environment isolation
- Create sandbox and production keys with one-time secret display; persist only a SHA-256 digest and a short public prefix.
- List key metadata, revoke and rotate keys, expiration, scopes, last-used timestamps, and security-event auditing.
- Determine environment from server-side deployment configuration, never from a caller-controlled header.
- Reject environment mismatches with HTTP 403 and stable error code `API_KEY_ENVIRONMENT_MISMATCH`.
- Keep legacy `REGISTRY_API_KEYS` as a documented migration mechanism; production rollout requires explicit migration to managed keys.
- Gate key-management endpoints behind a separate server-side management token until the application has authenticated user sessions and organization roles. Do not expose this token to React.
- Release gate: tests for environment mismatch, revoked/expired keys, scope enforcement, one-time secrets, and no raw secret in logs.

## Phase 2 — Ingestion reliability
- [x] Add XLSX support with read-only row iteration, archive signature checks, and uncompressed-size/entry limits; CSV remains streaming and PDFs remain bounded/manual-review.
- [x] Add a non-persistent CSV/XLSX preview endpoint with sample rows and size limits.
- [x] Expose measured identifier-coverage and duplicate-review summary metrics, with definitions that explicitly distinguish coverage from legal verification.
- [x] Add record-level completeness scoring with field-level evidence and flags; never label the score as legal verification.
- Persist upload checksum, content signature, source attribution, progress, retry count, and worker lease.
- [ ] Add preview/field mapping, row-level validation, duplicate submission handling, dead-letter export, and safe retry/resume.
- Add malware scanning as a provider adapter with an explicit unavailable state; never claim a scan passed if no scanner ran.
- Release gate: large-file, malformed-file, duplicate-upload, retry, worker-crash, and row-isolation tests.

## Phase 3 — Registry quality and entity resolution
- Add versioned validation rules, completeness/quality indicators, freshness and source confidence.
- Detect exact identifier conflicts and fuzzy-name candidates; name similarity alone must never auto-merge records.
- Record source lineage and change history; invalidate cache only after committed updates.
- Release gate: deterministic scoring, conflict cases, false-positive tests, and explainable evidence.

## Phase 4 — Kenya verification providers
- [x] Add verification case/provider-check persistence and endpoints that clearly report BRS, KRA, and Peleza as not configured; no fake provider response is generated.
- Add adapter contracts for BRS, KRA, and approved commercial providers.
- Store provider, request correlation, response classification, evidence reference, timestamps, retries, and manual-review state.
- Use sandbox/mock adapters only in tests. Live adapters require approved access, credentials, terms, and provider documentation.
- Treat timeout, unavailable, no-match, and verified as distinct states; do not infer legal verification from imported data.
- Release gate: contract tests, timeout/retry tests, secrets redaction, and explicit provider readiness.

## Phase 5 — Developer experience
- Publish OpenAPI examples and language-specific integration snippets.
- Add API usage metrics, request/correlation lookup, idempotency guidance, webhook endpoints, signed deliveries, retry policy, and delivery history.
- Add version/deprecation policy and sandbox fixtures.
- Release gate: examples run against sandbox and contain no production credentials.

## Phase 6 — Operations and reliability
- [x] Expand health/readiness diagnostics for database, configured object storage, Redis, queue depth/age, and explicitly report that worker heartbeat is not yet instrumented.
- [ ] Add a persisted worker heartbeat, alert thresholds, incident runbooks, backup/restore drills, SLO dashboards, and controlled retry/replay tooling.
- Add alert thresholds, incident runbooks, backup/restore drills, SLO dashboards, and controlled retry/replay tooling.
- Release gate: tested failure scenarios and a documented recovery procedure.

## Phase 7 — Organization access and data governance
- Integrate with the actual authenticated tenant identity system before offering customer self-service key management.
- Add role-based access, tenant-scoped queries, audit access, data retention/deletion workflows, and private evidence access.
- Add upload malware scan/quarantine and sensitive-data redaction.
- Release gate: cross-tenant isolation tests and access-control review. A caller-supplied tenant ID is never an authorization mechanism.

## Phase 8 — Commercial and customer operations
- Add usage metering, quotas, plan entitlements, organization monitoring, bulk lookups, subscriptions, and scheduled reports.
- Enforce limits server-side; dashboard numbers are derived from persisted usage events.
- Release gate: concurrency/idempotency tests, quota boundary tests, and customer-visible usage definitions.

## Delivery and safety
- Work in reviewable branches and pull requests; do not merge or deploy automatically.
- Database changes are additive and shipped as migrations. Review live schema before applying.
- Do not put service secrets in frontend code, public fixtures, commits, or logs.
- External integrations remain unconfigured until credentials and permissions are supplied.
- Each phase must include automated tests, documentation, migration notes, and a rollback plan.
