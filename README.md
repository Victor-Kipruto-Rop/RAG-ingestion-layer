# PesaGuard Registry Datasource

A standalone organization-data warehouse for PesaGuard. It imports authorized registry datasets, normalizes and searches organization records, preserves source provenance and change history, and exposes a protected internal API.

This is a datasource, not the PesaGuard customer onboarding system and not an authority that independently certifies companies. Imported data is marked unverified unless a trusted verification workflow establishes otherwise.

## Local development

1. For Windows local testing, copy `example.env` to `.env` and replace `REGISTRY_API_KEYS` with a long random local-only key.
2. Run `docker compose -f docker-compose.windows.local.yml up -d --build` to start the API, dashboard, and independent worker with one shared SQLite database and local file storage. This configuration is isolated from production Supabase and R2.
3. Open the dashboard at `http://localhost:5173` and API docs at `http://localhost:8000/docs`. Use only the local-only API key in the dashboard.
4. The guided Windows startup and stop scripts are `scripts/start-windows-local.ps1` and `scripts/stop-windows-local.ps1`.
5. Follow [`docs/windows-local-worker.md`](docs/windows-local-worker.md) to upload the fictional CSV fixture and verify that the worker processes it.
6. Tests: `PYTHONPATH=backend pytest -q` (run from the repository root in a Python environment with backend requirements installed).

Do not commit `.env`, API keys, database URLs, or R2 credentials.

## Database migrations

Apply in order to PostgreSQL/Supabase:
1. `database/migrations/001_initial.sql`
2. `database/migrations/002_provenance_and_versions.sql`
3. `database/migrations/003_durable_ingestion_sources.sql`
4. `database/migrations/004_ingestion_retry_leases.sql`
5. `database/migrations/005_warehouse_bronze_gold.sql`
6. `database/migrations/006_failed_imports_dlq.sql`
7. `database/migrations/007_ingestion_row_progress.sql`
8. `database/migrations/008_job_correlation_id.sql`
9. `database/migrations/009_api_key_lifecycle.sql`

Set `APP_ENV=production` only after migrations are applied. Production startup intentionally does not create tables automatically.

## Warehouse layers\n\n- **Bronze:** `warehouse_raw_imports` records raw object metadata, checksum, source, size, and ingestion status; raw files are stored in private R2.\n- **Silver:** `warehouse_organizations` is a read-only view over canonical `internal_organizations` records, with normalization, provenance and data-quality state.\n- **Gold:** `warehouse_access_logs` stores lookup/API performance telemetry without API keys or raw credentials.\n\nConfigure `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME` in the deployment environment. Create the private bucket in Cloudflare R2 first; the repository cannot create a Cloudflare account resource without authorized Cloudflare access.\n\n
## Production hardening

The current implementation work is tracked in [the phased production hardening roadmap](docs/production-hardening-roadmap.md). Review [database migration safety](docs/database-migrations.md) before running Alembic against any existing database, and see [internal API security](docs/internal-api-security.md) and [large-file ingestion](docs/large-file-ingestion.md) for HMAC signing, replay protection, rate limits, cache behavior and metrics.

- CSV ingestion uses a disk-backed spool, bounded database batches, and persisted row progress for safe retry/resume; XLSX uses a read-only parser with archive expansion limits; PDF diagnostics remain bounded and manual-review-only.
- Invalid row diagnostics are written to the restricted dead-letter table with sensitive row values masked.
- HMAC signing is optional during caller migration. Do not enable REQUIRE_HMAC until PesaGuard callers send the documented signature headers and REDIS_URL is configured.
- Distributed rate limiting and Redis cache-aside are active only when REDIS_URL is configured; the no-Redis fallback is per-process and is not a distributed security boundary.
- Set METRICS_TOKEN to expose the protected Prometheus endpoint. Keep it private and scrape over a restricted network path.
- The production frontend image needs VITE_API_BASE_URL set at build time to the deployed API URL; the default localhost URL is for local development only.

## PesaGuard service connection

Configure `REGISTRY_API_KEYS` on this service and the matching secret in the PesaGuard backend only. PesaGuard should call this service over HTTPS with `X-API-Key`. Never place this service key in React, a mobile application, or any browser-visible environment variable. Use a separate admin authentication mechanism for the dashboard.

Example request:

    GET /api/v1/registry/lookup?reg_no=CPR-123456
    X-API-Key: <server-side-secret>

The API returns found, a matching organization when present, source metadata, data-quality state, and timestamps. A local record is not proof of current legal status or authoritative KYB verification.

## Ingestion flow

- `GET /api/v1/quality/summary` (identifier coverage and duplicate-review indicators; not authoritative verification)
- `POST /api/v1/ingestion/preview` returns a non-persistent sample of CSV/XLSX files up to 5 MiB; it does not create an ingestion job.
- `POST /api/v1/ingestion/uploads` validates file size/type and signatures, stores the original in R2 (or local development storage), creates a durable queued job, and returns HTTP 202. CSV is streamed; XLSX uses read-only parsing with compressed/uncompressed size and archive-entry limits.
- Run one or more `registry-worker` processes to process queued CSVs. PostgreSQL row locks with `SKIP LOCKED` allow multiple workers to claim separate jobs.
- Jobs use `Idempotency-Key` to safely replay a request when supplied; retries are bounded by `WORKER_MAX_ATTEMPTS`, use exponential delay from `WORKER_RETRY_SECONDS`, and stale processing jobs are recovered after `WORKER_STALE_AFTER_SECONDS`.
- Row failures are persisted and can be queried through `GET /api/v1/ingestion/jobs/{job_id}/errors`.
- PDF uploads are retained and moved to `NEEDS_PDF_PROCESSING`; extraction/OCR is not enabled and the API does not pretend otherwise.
- Register dataset metadata with `POST /api/v1/sources`, then pass `X-Registry-Source: <source_key>` when uploading. Source fields capture jurisdiction, licence, freshness SLA and precedence.

## Core endpoints

- `GET /health/live`, `GET /health/ready`
- `GET /api/v1/registry/lookup?reg_no=...` or `?tax_pin=...`
- `GET /api/v1/registry/search?q=...`
- `GET /api/v1/organizations?page=1&page_size=25`
- `GET/POST /api/v1/sources`
- `POST /api/v1/ingestion/uploads`
- `GET /api/v1/ingestion/jobs`
- `GET /api/v1/ingestion/jobs/{job_id}/errors`
- `GET /api/v1/metrics/summary`
- `GET /api/v1/exports/organizations.csv`

## Production requirements and current boundaries

- Configure PostgreSQL, private R2, TLS, backups, monitoring, and a separate dashboard/admin authentication layer before exposing the service.
- Never send the PesaGuard service API key to the browser. The existing React dashboard API-key pattern is not production-safe; do not expose the dashboard to untrusted users until replaced with server-side session auth.
- Use a separate worker deployment from the API. Keep API and worker on the same durable database and object store. Local storage is only for development and requires a shared volume between containers.
- CSV rows are processed asynchronously, but each bounded CSV object is currently read into worker memory; use streaming parsing for very large files.
- PDF extraction/OCR and actual government/commercial registry connectors are not activated.
- Run CI and production integration tests before relying on this service for live decisions.

See `docs/ARCHITECTURE.md` for the operating contract and scale roadmap.


## Windows local worker test

For a safe Windows/Docker Desktop smoke test that uses a shared local SQLite database and local file storage (not production Supabase or R2), follow [`docs/windows-local-worker.md`](docs/windows-local-worker.md). It includes a fictional CSV fixture at [`samples/test-organizations.csv`](samples/test-organizations.csv) and uses [`docker-compose.windows.local.yml`](docker-compose.windows.local.yml) to run the API and worker together. Do not put production credentials in this local test configuration.


A safe Windows local environment template is provided as [`example.env`](example.env). Never commit `.env`, API keys, database URLs, or R2 credentials.


## Phased implementation

See [implementation phases](docs/implementation-phases.md) for the delivery roadmap and release gates. The managed API-key lifecycle is documented in [API key lifecycle](docs/api-key-lifecycle.md).

### Managed API keys (initial implementation)

- Configure `PESAGUARD_DATASOURCE_ENVIRONMENT=sandbox` on a sandbox deployment or `production` on production. The server setting is authoritative; request headers cannot switch environments.
- Apply migration `009_api_key_lifecycle.sql` to a non-production PostgreSQL database first.
- Configure `API_KEY_MANAGEMENT_TOKEN` as a high-entropy server-side deployment secret. Do not expose it to browser code.
- The operator routes are `POST/GET /api/v1/admin/api-keys`, `POST /api/v1/admin/api-keys/{id}/revoke`, and `POST /api/v1/admin/api-keys/{id}/rotate`; they require `X-Key-Management-Token`.
- Managed key secrets are returned only once. The database stores only a SHA-256 digest and a public prefix. Managed keys are checked against the server deployment environment and scopes.
- Legacy `REGISTRY_API_KEYS` remain available during caller migration. Do not revoke them until each trusted service caller has been migrated and verified.
- The current application has no verified customer login/organization-owner identity in this service. These management routes are operator-only; do not expose them as a customer self-service UI until authenticated tenant roles are integrated.
