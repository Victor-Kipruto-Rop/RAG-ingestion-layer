# Phased implementation status

This document tracks the product-feature roadmap for PesaGuard Datasource. A phase is only marked complete when its implementation and relevant checks have evidence; planned work is not described as shipped.

## Phase 1 — API key security and environment isolation
**Status: blocked on dashboard identity/authentication foundation.**

Required before enabling customer-managed keys: authenticated user sessions, organization membership/role checks, and a trusted organization context. The current datasource API uses deployment-level `REGISTRY_API_KEYS` / optional HMAC, and the dashboard is explicitly not safe for untrusted users because it has no verified session-authentication layer. Do not expose key creation/revocation to the public dashboard until that foundation exists.

Implementation requirements:
- Separate sandbox and production key namespaces, server-side environment enforcement, one-time secret display, hash-only storage, revocation/rotation/expiry, scoped permissions, audit events and misuse alerts.
- Sandbox credentials must be rejected by production deployments with a stable `API_KEY_ENVIRONMENT_MISMATCH` error and an audit event.
- Never treat a caller-supplied environment header or organization ID as authorization.

## Phase 2 — Ingestion reliability
**Status: incremental implementation in progress.**

- CSV ingestion already uses disk-backed spooling, bounded batches, persisted row progress, retries and a dead-letter table.
- Added strict parser validation for duplicate/blank headers and rows containing more values than the header. Previously, extra cells could be silently discarded by `csv.DictReader`.
- Added regression tests for normal rows, malformed headers, extra cells, record limits and short rows.
- Remaining: run CI, add interruption/retry integration tests, test representative large files, and verify migration state against the live schema before any production migration.

## Phase 3 — Data quality and registry intelligence
- Add measurable completeness/quality summaries, explicit validation outcomes, duplicate candidate evidence, provenance/freshness and human-review queues.
- Name similarity must never auto-merge entities; preserve conflicting identifier evidence and review state.

## Phase 4 — Registry/provider integrations
- Build provider adapters with timeouts, bounded retries, circuit breakers, normalized outcomes, evidence provenance and manual-review fallbacks.
- Keep BRS/KRA/provider calls disabled until credentials, permissions and production contracts are verified.

## Phase 5 — Developer experience
- Add environment-aware API documentation, request examples, scopes, rate-limit headers, idempotency guidance, changelog, webhooks and delivery history.
- Keep server-side secrets out of browser bundles.

## Phase 6 — Production operations
- Add actionable health/readiness checks, queue monitoring, alert thresholds, audit search, backup/restore evidence, dependency scanning and safe rollback runbooks.
- Do not claim SLOs without measured load-test results.

## Phase 7 — Commercial and customer controls
- Add plans/quotas, usage metering, customer-level source entitlements and billing only after identity, tenant isolation, key security and reliable metering are production-ready.

## Release safety
- No production database migration or deployment is performed by this implementation branch.
- A pull request must be reviewed and checks must pass before merge.
