# PesaGuard Registry Datasource: Architecture and operating contract

## Mission

This repository is an independently deployable organization-data warehouse and internal datasource for PesaGuard. It stores authorized source datasets, normalizes them, exposes fast lookups, and preserves provenance and change history. It is not the customer onboarding service and does not itself certify an organization as genuine.

## System boundaries

- **PesaGuard application:** owns users, tenants, organization profiles, verification cases, risk decisions, and customer-facing workflow.
- **Registry datasource:** owns imported source records, dataset ingestion, normalization, search, record provenance, version history, data-quality state, and service API.
- **Supabase/PostgreSQL:** source of truth for normalized records, jobs, audit events, and version history. Apply SQL migrations in order.
- **Cloudflare R2:** private object storage for original source files and supporting source artifacts. Keep bucket private; do not return raw object keys or public URLs to customers.
- **PesaGuard integration:** server-to-server HTTPS from PesaGuard backend to datasource. The registry key must never be embedded in a browser bundle, mobile app, or public frontend.

## Record trust and provenance

Every response should make it possible to answer: what data was returned, where it came from, when it was ingested/last observed, and whether it was independently verified. Current imported rows use data_quality_status=IMPORTED_UNVERIFIED. This is deliberately not the same as verified. A name similarity result is a candidate, never an identity assertion. Do not infer active legal status from a missing or ambiguous source value.

The source file and row are retained, alongside source name/record ID and a version snapshot on create/update. When a new authorized source becomes available, add a source catalogue and explicit source publication/effective dates rather than silently overwriting provenance.

## Ingestion lifecycle

1. Authenticate the operator/service.
2. Validate file extension, byte limit, content signature, and parser limits.
3. Store the original file privately in R2 and record its object key.
4. Create an ingestion job and a correlation ID.
5. Parse and normalize records; report invalid rows explicitly.
6. Upsert by normalized registration number; only use tax PIN as a fallback identity when registration number is absent.
7. Store a record-version snapshot for created/updated records.
8. Commit counts, errors, and audit event atomically where possible.
9. Make the job result queryable and retryable.

**Current-release limitation:** CSV processing is now queued in the database and handled by a separate worker with bounded retries and row-level error records. The worker still reads each bounded object into memory; implement streaming parsing before increasing the upload limit. PDF upload is tracked but does not yet extract/import PDF records. Do not claim these paths are complete.

## API contract for PesaGuard

All /api/v1 routes require X-API-Key over HTTPS. Generate a high-entropy secret; configure the same secret only in the PesaGuard backend's secret store and this service's secret store. Use separate keys per environment and rotate by allowing two active keys briefly, then removing the old one.

- GET /api/v1/registry/lookup?reg_no=... — exact normalized registration-number lookup.
- GET /api/v1/registry/lookup?tax_pin=... — exact normalized tax PIN lookup.
- GET /api/v1/registry/search?q=...&limit=20 — substring search and PostgreSQL trigram candidates where configured. Fuzzy candidates must be reviewed; not proof of identity.
- GET /api/v1/organizations?page=1&page_size=25&q=... — paginated internal administration list.
- POST /api/v1/ingestion/uploads — bounded CSV or PDF upload; returns 202 and a durable job ID.\n- GET /api/v1/ingestion/jobs/{job_id}/errors — paginated row-level import failures.\n- GET/POST /api/v1/sources — dataset source catalogue.
- GET /api/v1/ingestion/jobs — ingestion job history.
- GET /api/v1/metrics/summary — warehouse counters.
- GET /api/v1/exports/organizations.csv — protected administrative export.
- /health/live and /health/ready — infrastructure health checks.

A successful lookup means a record was found in this local warehouse, not that a government agency has verified it. Preserve source, data_quality_status, and timestamps in the consuming PesaGuard verification case.

## Production scale requirements

Before accepting large or mission-critical datasets, complete these controls:

1. Durable background queue, retry/backoff, dead-letter state, and idempotent job execution.
2. Streaming/multipart R2 uploads and chunked parsing; avoid whole-file memory reads.
3. Per-row validation results and downloadable error report; do not silently skip invalid rows.
4. Source catalogue, dataset checksums, import deduplication, freshness SLA, and explicit source precedence rules.
5. PostgreSQL indexes and pg_trgm; query plans checked with realistic volumes. Use cursor/keyset pagination for large scans.
6. Separate admin identity/session auth from the service-to-service API key. Do not expose the internal key in a React app. Dashboard currently needs a dedicated admin-auth design before production use.
7. Rate limits, request-size limits at proxy, request IDs, structured logs, metrics, alerting, backups/restore drills, and database migration automation.
8. Private R2 bucket, least-privilege credentials, malware scanning/quarantine for untrusted uploads, retention/deletion policy, and encryption in transit.
9. Tests against PostgreSQL as well as SQLite, concurrency tests for duplicate upserts, and CI that runs backend tests and frontend production build.
10. Legal basis/licensing for every imported dataset and a documented correction process.

## No false claims

Never fabricate data, source provenance, government API results, verification outcomes, or successful integrations. If a provider is unavailable, mark it unavailable and keep the record unverified.
