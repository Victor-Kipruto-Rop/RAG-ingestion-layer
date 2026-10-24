## GitLab CI/CD

GitLab CI/CD configuration is in `.gitlab-ci.yml`. Setup, required CI/CD variables, staging deployment, runner requirements, and troubleshooting are documented in [GitLab CI/CD setup](docs/gitlab-ci-setup.md). Merge request and issue templates are in `.gitlab/`.

The GitLab pipeline is staging-scoped: validation/test jobs can run on merge requests, while Cloudflare Pages deployment and ingestion operations are manual and restricted to `chore/production-ci-release-gates`. Importing this repository from GitHub does not guarantee ongoing synchronization; keep the GitLab branch updated before expecting its pipeline to run the latest changes. Never use production credentials in staging CI variables.

## Developer platform and SDKs

The public developer control plane is implemented in `frontend/src/DeveloperPlatformApp.jsx` and `backend/src/developer_platform.py`. It includes email OTP signup and recovery, Google/GitHub OAuth configuration, revocable sessions, tenant API-key management, production-access requests, signed webhooks, API Explorer, and multi-language integration examples.

- [Developer platform operations guide](docs/developer-platform.md)
- [Resend email, OTP signup/recovery, and session security setup](docs/developer-platform-email-auth.md)
- [Complete email catalogue and sending algorithms](docs/email-notification-catalog-and-algorithms.md) — transactional, security, API-key, webhook, production access, ingestion, lifecycle and consent-based marketing emails.
- [Staging release acceptance checklist](docs/release-acceptance-staging.md) — mandatory evidence gates for OAuth, Resend/SMTP delivery, environment isolation, API keys, webhooks, and session revocation.
- [Python SDK](sdks/python/README.md)
- [JavaScript SDK](sdks/javascript/README.md)
- Sandbox base URL: `https://sandbox-api.pesaguard.co.ke` with `pg_sandbox_` keys.
- Production base URL: `https://api.pesaguard.co.ke` with `pg_live_` keys; production access requires verified workspace and operator approval.

The SDKs are source-controlled and have CI test targets; they are not published to PyPI/npm yet. Provider OAuth, Resend (or explicit SMTP fallback) delivery, webhook encryption, PostgreSQL, Redis, and separate sandbox/production deployments must be configured and verified in the target environment before calling these flows operational in production.

# PesaGuard Registry Datasource

A standalone organization-data warehouse for PesaGuard. It imports authorized registry datasets, normalizes and searches organization records, preserves source provenance and change history, and exposes a protected internal API.

This is a datasource, not the PesaGuard customer onboarding system and not an authority that independently certifies companies. Imported data is marked unverified unless a trusted verification workflow establishes otherwise.

## Dashboard documentation and operator OAuth

The dashboard includes a Documentation section in the sidebar with platform overview, API reference links, authentication guidance, pipeline and data-quality guidance, architecture/technology mapping, and operations/security checklists.

Google and GitHub OAuth are supported for **existing allowlisted dashboard operators only**. They do not provide open self-service signup and do not grant operator access to arbitrary provider accounts.

1. Create OAuth applications in Google Cloud Console and GitHub Developer Settings.
2. Register exact callbacks:
   - `https://YOUR_PUBLIC_HOST/api/v1/admin/oauth/google/callback`
   - `https://YOUR_PUBLIC_HOST/api/v1/admin/oauth/github/callback`
3. Configure `PUBLIC_BASE_URL`, the corresponding `GOOGLE_OAUTH_CLIENT_ID/SECRET` and/or `GITHUB_OAUTH_CLIENT_ID/SECRET`, plus `ADMIN_OAUTH_ALLOWED_EMAILS` containing the exact verified operator email addresses.
4. Use HTTPS and set `SESSION_COOKIE_SECURE=true` in production. Keep client secrets in the deployment secret manager; never put them in frontend environment variables.
5. Verify `GET /api/v1/admin/oauth/providers` reports the expected enabled providers, then test login, state mismatch rejection, unallowlisted accounts and logout in staging.

The internal operator dashboard remains separate from the public developer platform. The public developer platform has its own account/workspace/session models, OTP-based signup and password recovery, OAuth, profile and session endpoints. Keep the two identity domains separate. Developer email delivery still requires configured Resend or SMTP, verified sender-domain DNS, and target-environment verification; durable outbox processing and provider bounce/complaint callbacks remain release requirements.

### Operator profile and notifications

- The Profile sidebar page reads and updates the persisted operator display name and contact email through `/api/v1/admin/profile`.
- The Notifications page derives operational alerts from persisted ingestion jobs. Read state is persisted through `/api/v1/admin/notifications` and `POST /api/v1/admin/notifications/read`.
- Apply database migrations before using these endpoints: `cd backend && alembic upgrade head`.
- These are operator profile metadata and operational job alerts, not a multi-user signup system or email/push notification delivery service.

## Local development

1. For Windows local testing, copy `.env.example` to `.env` and replace `REGISTRY_API_KEYS` with a long random local-only key.
2. Run `docker compose -f docker-compose.windows.local.yml up -d --build` to start the API, dashboard, and independent worker with one shared SQLite database and local file storage. This configuration is isolated from production Supabase and R2.
3. Open the dashboard at `http://localhost:5173` and API docs at `http://localhost:8000/docs`. Sign in with the dashboard admin password (see `ADMIN_PASSWORD_HASH` in `.env.example`); the browser never receives the service API key.
4. The guided Windows startup and stop scripts are `scripts/start-windows-local.ps1` and `scripts/stop-windows-local.ps1`.
5. Follow [`docs/windows-local-worker.md`](docs/windows-local-worker.md) to upload the fictional CSV fixture and verify that the worker processes it.
6. Tests: `pip install -r backend/requirements-dev.txt && pytest -q` from the repository root. Set `TEST_DATABASE_URL` and `TEST_PG_ADMIN_URL` to also run the suite and the SQL-migration/RLS checks on PostgreSQL.

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
9. `database/migrations/009_environment_scoped_api_keys.sql`
10. `database/migrations/010_job_heartbeat_and_search_indexes.sql`
11. `database/migrations/011_rls_lockdown.sql`

Alembic (`backend/migrations`) is the schema source of truth; the SQL files and `supabase/migrations` mirror it for SQL-editor deployments. CI fails if either drifts from the models (see `backend/tests/test_schema_drift.py`).

Set `APP_ENV=production` only after migrations are applied. Production startup intentionally does not create tables automatically.

## Warehouse layers

- **Bronze:** `warehouse_raw_imports` records raw object metadata, checksum, source, size, and ingestion status; raw files are stored in private R2.
- **Silver:** `warehouse_organizations` is a read-only view over canonical `internal_organizations` records, with normalization, provenance and data-quality state.
- **Gold:** `warehouse_access_logs` stores lookup/API performance telemetry without API keys or raw credentials.

Configure `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME` in the deployment environment. Create the private bucket in Cloudflare R2 first; the repository cannot create a Cloudflare account resource without authorized Cloudflare access.


## Production hardening

The current implementation work is tracked in [the phased production hardening roadmap](docs/production-hardening-roadmap.md). The broader premium UX and production-readiness execution plan is [here](docs/premium-production-roadmap.md), with strict phase-by-phase agent instructions in [prompts/](prompts/README.md) and evidence reports in [docs/phase-reports/](docs/phase-reports/). Review [database migration safety](docs/database-migrations.md) before running Alembic against any existing database, and see [internal API security](docs/internal-api-security.md) and [large-file ingestion](docs/large-file-ingestion.md) for HMAC signing, replay protection, rate limits, cache behavior and metrics.

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
- The dashboard signs in with a dedicated admin password and an HttpOnly, SameSite=Strict session cookie plus a per-session CSRF token. The service API key is never sent to the browser. Serve the dashboard and API over HTTPS and set `SESSION_COOKIE_SECURE=true`.
- Use a separate worker deployment from the API. Keep API and worker on the same durable database and object store. Local storage is only for development and requires a shared volume between containers.
- CSV rows are processed asynchronously, but each bounded CSV object is currently read into worker memory; use streaming parsing for very large files.
- PDF extraction/OCR and actual government/commercial registry connectors are not activated.
- Run CI and production integration tests before relying on this service for live decisions.

See `docs/ARCHITECTURE.md` for the operating contract and scale roadmap.


## Windows local worker test

For a safe Windows/Docker Desktop smoke test that uses a shared local SQLite database and local file storage (not production Supabase or R2), follow [`docs/windows-local-worker.md`](docs/windows-local-worker.md). It includes a fictional CSV fixture at [`samples/test-organizations.csv`](samples/test-organizations.csv) and uses [`docker-compose.windows.local.yml`](docker-compose.windows.local.yml) to run the API and worker together. Do not put production credentials in this local test configuration.


A safe Windows local environment template is provided as [`.env.example`](.env.example). Never commit `.env`, API keys, database URLs, or R2 credentials.


## Sandbox and production API keys

See [environment-scoped API key setup](docs/environment-scoped-api-keys.md). User-issued keys are tied to one environment and organization. Sandbox keys are rejected by production deployments and production keys are rejected by sandbox deployments. Key management requires a trusted PesaGuard-issued access token; configure the JWT issuer, audience and signing secret server-side. Apply migration 009 before enabling this feature. Do not expose `REGISTRY_API_KEYS` in browser code.


## Operator authentication setup

See [`docs/operator-auth-setup.md`](docs/operator-auth-setup.md) for database migrations, allowlisted sign-up, email OTP, password recovery, Google/GitHub OAuth, and persisted session revocation configuration.

## GitLab CI/CD (staging)

GitLab CI/CD is configured in [`.gitlab-ci.yml`](.gitlab-ci.yml). Follow the
[GitLab setup and operations guide](.gitlab/SETUP.md) for repository import and
sync, runners, CI/CD variables, Cloudflare Pages deployment, staging ingestion
jobs, security gates and troubleshooting.

The pipeline runs validation on `main` and staging feature branches. Cloudflare Pages deployment and ingestion operations remain manual. Configure staging-only variables before running those jobs; never reuse production credentials or data resources.

For a no-paid-Render-resources profile, review [`render.staging-free.yaml`](render.staging-free.yaml) and [`docs/STAGING_FREE_TIER.md`](docs/STAGING_FREE_TIER.md). This profile reuses the existing Supabase staging database and free Redis; it intentionally omits the background worker because Render does not offer a free worker plan. Asynchronous ingestion is therefore not end-to-end operational under this profile.
