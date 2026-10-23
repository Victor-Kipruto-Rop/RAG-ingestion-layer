# PesaGuard Datasource implementation phases

This file is the implementation ledger for the Datasource repository. "Implemented" means the repository contains code for the capability; it does not mean production credentials, third-party contracts, database migrations, or deployment settings have been applied.

## Phase 1 — API key security and environment isolation

**Repository implementation:** managed key creation/listing/rotation/revocation, one-time secret display, SHA-256 digest storage, scopes, expiration, last-used timestamps, security-event logging, environment mismatch rejection, and operator-only administration via `DATASOURCE_ADMIN_TOKEN`.

- Key prefixes: `pg_sandbox_...` and `pg_live_...`.
- The server's `DATASOURCE_ENVIRONMENT` (or `APP_ENV` fallback) determines the environment. A request header cannot override it.
- A managed sandbox key sent to a production deployment returns HTTP 403 with `API_KEY_ENVIRONMENT_MISMATCH`; the attempt is logged without storing the raw key.
- Administration is **operator-only**, not tenant self-service. Do not expose the admin token to customers, browser bundles, or public repositories.
- Migration `database/migrations/009_managed_api_keys.sql` must be reviewed and applied separately to each environment before managed keys can be used.
- Existing `REGISTRY_API_KEYS` credentials remain a legacy compatibility path. Remove or rotate legacy credentials when moving an environment to managed keys so they do not undermine the intended operational separation.

## Phase 2 — Reliable ingestion

**Repository implementation:** CSV/PDF upload validation, private object-storage flow, SHA-256 duplicate detection, idempotency keys, correlation IDs, asynchronous jobs, retry state, row progress, row-level errors, failed-import/DLQ support, and upload completion checks for direct uploads.

Remaining operational requirements: apply migrations 007–009 in order, confirm worker deployment and private bucket policy, configure malware scanning/quarantine before accepting untrusted documents at scale, and exercise failure/retry/restore scenarios in staging. PDF storage is not proof that every PDF has been successfully extracted.

## Phase 3 — Data quality and registry intelligence

**Repository implementation:** quality summary metrics, stale-source reporting, quality rules catalog, source provenance and record versions, duplicate-file detection, and fuzzy name-match candidates.

Matching is advisory. Do not auto-merge entities or treat imported records, a fuzzy match, a missing field, or a quality score as legal identity verification. Rule editing, full field-level conflict resolution, and a complete human-review workflow remain follow-on work.

## Phase 4 — External verification integrations

**Repository implementation:** provider-candidate response shapes and source metadata can support adapters; the dashboard labels external verification as not configured when no real connection is present.

**Not production-integrated by this code alone:** Kenya BRS, KRA, IPRS, Peleza, or other commercial/government APIs. Each requires approved access, documented permitted use, credentials stored server-side, provider-specific contract tests, rate-limit/retry policy, response provenance, and a manual-review fallback. Never fabricate a successful provider result.

## Phase 5 — Developer experience

**Repository implementation:** OpenAPI docs, protected lookup/search/export endpoints, paginated organization/job responses, idempotency/correlation support, API key scopes, and a dashboard API-key operator view.

Remaining: public developer onboarding and customer-specific accounts, webhook subscription/delivery management, SDKs, changelog/version policy, and self-service tenant access. These depend on a proper tenant/user identity and authorization model; the operator token is not a substitute for one.

## Phase 6 — Operations and security

**Repository implementation:** live/readiness/health endpoints, protected Prometheus metrics, request correlation, structured request logs, database query timing, warehouse access logs, rate limiting, optional HMAC replay protection, source freshness, and API-key security events.

Before production: validate dashboards/alerts, backups and restore, key rotation runbook, retention and incident procedures, access review, upload malware scanning, and load/abuse tests. A health response only describes checks actually performed by that endpoint.

## Phase 7 — Commercial and customer management

**Status:** intentionally not represented as completed. Plans, billing, customer subscriptions, usage quotas/invoices, paid data licensing, and service-level commitments require business/legal decisions and a tenant/billing model. Do not charge users or advertise SLAs based only on the current operator dashboard.

## Deployment gates

1. Keep the dashboard and API on a review branch until CI passes.
2. Apply the migrations in order to a disposable/staging database first; inspect schema and rollback/recovery options.
3. Deploy separate sandbox and production services with `DATASOURCE_ENVIRONMENT=sandbox` and `DATASOURCE_ENVIRONMENT=production` respectively.
4. Configure a unique high-entropy `DATASOURCE_ADMIN_TOKEN` as a server secret per environment.
5. Create a sandbox key and verify it works only against sandbox; use the same sandbox key against production and confirm the 403 mismatch plus security event.
6. Create a production key only after staging checks; store it in a secret manager, not in frontend code or source control.
7. Remove legacy `REGISTRY_API_KEYS` when all legitimate callers have migrated, then re-test.
8. Never apply production migrations or deploy automatically from this implementation branch.
