# PesaGuard Registry Datasource

A standalone organization-data warehouse for PesaGuard. It imports authorized registry datasets, normalizes and searches organization records, preserves source provenance and change history, and exposes a protected internal API.

This is a datasource, not the PesaGuard customer onboarding system and not an authority that independently certifies companies. Imported data is marked unverified unless a trusted verification workflow establishes otherwise.

## Local development with Docker (Supabase + R2)

1. Install and start Docker Desktop (Linux containers), then confirm `docker info` succeeds.
2. Copy `example.env` to `.env`. Configure `DATABASE_URL` with the Supabase sandbox PostgreSQL connection string, all four required R2 settings with a private sandbox bucket/token, and a long random sandbox-only `REGISTRY_API_KEYS` secret.
3. Set `APP_ENV=development`, `DATASOURCE_ENVIRONMENT=sandbox`, and `CONFIRM_SANDBOX_TARGET=YES` only after verifying the Supabase project and R2 bucket are dedicated sandbox resources.
4. Review and apply the SQL files under `database/migrations/` to the intended sandbox database. Docker deliberately does not run migrations automatically against Supabase.
5. Run `docker compose config --quiet`, then `docker compose up -d --build`. Compose starts the API, local Redis, the local ingestion worker, and the React dashboard. API and worker use the same Supabase PostgreSQL database and Cloudflare R2 bucket; the worker runs locally in Docker.
6. Open the dashboard at `http://localhost:5173`, API docs at `http://localhost:8000/docs`, liveness at `http://localhost:8000/health/live`, and readiness at `http://localhost:8000/health/ready`.
7. Configure the PesaGuard Core API backend with the datasource URL and the matching sandbox secret on the server side only. See [`docs/windows-local-worker.md`](docs/windows-local-worker.md) for connection guidance.
8. View status/logs with `docker compose ps` and `docker compose logs -f registry-api registry-worker registry-frontend`. Stop with `docker compose down`.

**Important:** the worker claims queued jobs from the configured database and writes job status, normalized records, and errors. Never point this local worker at production Supabase/R2 unless you explicitly intend it to process production data. Do not commit `.env`, API keys, database URLs, or R2 credentials. Backend tests: `PYTHONPATH=backend pytest -q`.

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

Set `APP_ENV=production` only after migrations are applied. Production startup intentionally does not create tables automatically.

## Warehouse layers\n\n- **Bronze:** `warehouse_raw_imports` records raw object metadata, checksum, source, size, and ingestion status; raw files are stored in private R2.\n- **Silver:** `warehouse_organizations` is a read-only view over canonical `internal_organizations` records, with normalization, provenance and data-quality state.\n- **Gold:** `warehouse_access_logs` stores lookup/API performance telemetry without API keys or raw credentials.\n\nConfigure `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME` in the deployment environment. Create the private bucket in Cloudflare R2 first; the repository cannot create a Cloudflare account resource without authorized Cloudflare access.\n\n
## Production hardening

The current implementation work is tracked in [the phased production hardening roadmap](docs/production-hardening-roadmap.md). Review [database migration safety](docs/database-migrations.md) before running Alembic against any existing database, and see [internal API security](docs/internal-api-security.md), [large-file ingestion](docs/large-file-ingestion.md), and the [release and operations runbook](docs/release-and-operations-runbook.md) for HMAC signing, replay protection, rate limits, cache behavior and metrics.

- CSV ingestion uses a disk-backed spool, bounded database batches, and persisted row progress for safe retry/resume; PDF diagnostics remain bounded and manual-review-only.
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

- `POST /api/v1/ingestion/uploads` validates the file size/type, stores the original in R2 (or local development storage), creates a durable queued job, and returns HTTP 202.
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


## Windows local worker

Follow [`docs/windows-local-worker.md`](docs/windows-local-worker.md) for the Supabase + R2 sandbox workflow. The fictional CSV fixture is at [`samples/test-organizations.csv`](samples/test-organizations.csv); `docker-compose.yml` runs the API and worker locally while persisting data to the configured external sandbox services. The startup script requires explicit sandbox confirmation. Never commit `.env`, API keys, database URLs, or R2 credentials.


## Managed sandbox and production API keys

The managed-key feature is additive and is disabled operationally until the database migration and server settings are configured.

1. Review and apply `database/migrations/009_managed_api_keys.sql` to the intended database. Do not run it against production without a schema backup and an approved change window.
2. Set `DATASOURCE_ENVIRONMENT=sandbox` on the sandbox deployment and `DATASOURCE_ENVIRONMENT=production` on the production deployment. The server's configured environment is authoritative; client headers cannot override it.
3. Set `DATASOURCE_ADMIN_TOKEN` to a strong secret in the server's secret manager. Do not add it to frontend build variables, source control, or a public-facing customer application.
4. Open the dashboard's **API Keys** page and enter the operator token. The page keeps it in memory only. Generate a key, copy the secret once, and store it in a secret manager.
5. Use sandbox keys only against the sandbox datasource URL. Production rejects sandbox keys with HTTP 403 and code `API_KEY_ENVIRONMENT_MISMATCH`; attempted misuse is recorded in `api_key_security_events` when the audit database is available.
6. Use scopes to limit access. Rotate/revoke keys when a secret is exposed or no longer needed. The database stores a SHA-256 digest, not the plaintext secret.

Managed key routes (operator token required):
- `GET /api/v1/admin/api-keys`
- `POST /api/v1/admin/api-keys`
- `POST /api/v1/admin/api-keys/{id}/rotate`
- `DELETE /api/v1/admin/api-keys/{id}`
- `GET /api/v1/admin/security-events?limit=100`

Data governance routes (API key required):
- `GET /api/v1/quality/summary`
- `GET /api/v1/quality/rules`
- `GET /api/v1/registry/match-candidates?q=...`
- `GET /api/v1/sources/freshness`
- `GET /api/v1/audit/logs?limit=100`

The operator token is a single-operator control, not end-user authentication. Do not expose key-management routes as customer self-service until a real identity provider, organization membership checks, and tenant-scoped authorization are implemented. Legacy `REGISTRY_API_KEYS` remain supported during migration and are not individually environment-scoped; migrate callers to managed keys before retiring the shared-key mechanism. BRS/KRA adapters are interfaces only until vendor-approved credentials and integration tests are completed.
