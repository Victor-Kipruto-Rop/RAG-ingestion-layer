# Windows local Docker stack: Supabase + Cloudflare R2

This setup runs the datasource API, Redis, React dashboard, and ingestion worker locally in Docker. The API and worker both read the same Supabase PostgreSQL connection string and Cloudflare R2 credentials from the root `.env` file. The worker runs on your computer; uploaded objects and registry/job data live in Supabase and R2.

## Important safety rule

**Use a dedicated sandbox Supabase project and a dedicated private sandbox R2 bucket. Do not point this worker at production by default.** The worker claims queued jobs from the configured database, so connecting it to a shared production database could cause it to process production jobs. It can also write normalized records, job statuses, row errors and audit events. A local Docker container does not make those writes local.

## Prerequisites

- Windows 10/11, Git, and Docker Desktop using Linux containers.
- A Supabase sandbox project with the required datasource SQL migrations applied.
- A private Cloudflare R2 sandbox bucket and an R2 API token with only the bucket permissions needed for this application.
- The PesaGuard Core API configured server-side to call this datasource using a sandbox API key.

Check Docker first:

```powershell
docker --version
docker compose version
docker info
```

## 1. Configure the environment

Copy the template and edit it:

```powershell
Copy-Item example.env .env
notepad .env
```

Set these values:

- `DATABASE_URL`: Supabase PostgreSQL connection string. Use the Supabase Session Pooler for application connections where appropriate, keep `sslmode=require`, and URL-encode special characters in the password. This app connects to Supabase through PostgreSQL/SQLAlchemy; it does not use the anon key as a database password.
- `REGISTRY_API_KEYS`: a long random sandbox-only datasource API key.
- `DATASOURCE_ENVIRONMENT=sandbox`.
- `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_BUCKET_NAME`: credentials and private bucket for the sandbox. `R2_ENDPOINT_URL` can remain blank to use the standard account endpoint.
- `REDIS_URL=redis://registry-redis:6379/0`. Inside Compose, use the service name, not `localhost`.
- `VITE_API_BASE_URL=http://localhost:8000`.

Do not paste Supabase passwords, R2 secrets, admin tokens, or production API keys into GitHub, frontend variables, screenshots, or support messages. The `.env` file is ignored by Git and must stay untracked.

## 2. Apply database migrations deliberately

The Compose stack **does not run migrations automatically**. This is intentional: the database URL points to a shared external service and automatic schema changes at container startup are unsafe.

For a new sandbox database, review the migration files in `database/migrations/` and apply them in the documented order using the Supabase SQL Editor or your approved migration process. The README lists the ordered migration sequence. Before upgrading an existing database, take a backup and compare its current schema with the migration files. Do not blindly replay initial migrations against an existing project.

At minimum, verify the schema includes the ingestion job columns used by the current code, including `correlation_id` and `last_processed_row`, and the managed API-key tables if you intend to use those routes. Do not run migrations against production without a reviewed change plan and explicit approval.

## 3. Validate and start

From the repository root:

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The stack runs:
- API: `http://localhost:8000`
- Swagger/OpenAPI: `http://localhost:8000/docs`
- Dashboard: `http://localhost:5173`
- Redis: private to the Compose network
- Worker: local process in its own container

Ports 8000 and 5173 bind to loopback only. The API and worker share the same environment values, Supabase database, Redis service and R2 bucket. The worker restarts automatically if it exits while Docker is running.

## 4. Connect the PesaGuard Core API

The Core API must call the datasource from its backend, never from browser code. Configure the Core API's server-side environment with the datasource base URL and the exact sandbox secret configured in `REGISTRY_API_KEYS`. Suggested variable names (use the actual names supported by the Core API repository):

```dotenv
PESAGUARD_DATASOURCE_BASE_URL=http://host.docker.internal:8000
PESAGUARD_DATASOURCE_API_KEY=<same-sandbox-secret-as-REGISTRY_API_KEYS>
PESAGUARD_DATASOURCE_TIMEOUT_SECONDS=10
```

Use `http://host.docker.internal:8000` when the Core API runs in another Docker Compose project on the same Windows machine. If the Core API service is added to this same Compose network, use `http://registry-api:8000`. If the Core API runs directly on Windows, use `http://localhost:8000`. For a deployed Core API, use the deployed datasource HTTPS URL and a secret stored in that backend's secret manager.

The datasource expects `X-API-Key: <secret>` for protected API routes. Never add this key to `VITE_*` variables or React code. The suggested Core API variable names are integration guidance; this repository does not configure the separate Core API service.

## 5. Verify worker processing

1. Check readiness and logs:

   ```powershell
   Invoke-WebRequest http://localhost:8000/health/ready
   docker compose logs --tail 100 registry-api
   docker compose logs --tail 100 registry-worker
   ```

2. Use the dashboard or Swagger to upload only a fictional CSV fixture to the sandbox datasource.
3. Check `GET /api/v1/ingestion/jobs` until the job reaches `COMPLETED`.
4. Confirm the imported test organizations appear in the sandbox database, and that the source object exists in the sandbox R2 bucket.
5. Check worker logs for failures. PDFs are diagnostic/manual-review only; text extraction does not independently verify an organization.

An automated smoke test is available at `scripts/test-local-stack.ps1`. It writes records and queues jobs in whichever database and bucket are configured in `.env`; run it only after confirming these are sandbox resources.

## Logs and shutdown

```powershell
docker compose logs -f registry-api registry-worker registry-redis registry-frontend
docker compose down
```

Normal shutdown preserves the external Supabase and R2 data. It does not delete cloud resources or queued jobs. `docker compose down -v` only removes the local frontend dependency volume; it does not reset Supabase or delete R2 objects.

## Troubleshooting

- **Compose says DATABASE_URL is missing:** set a valid Supabase PostgreSQL URL in `.env`.
- **Database connection fails:** check host, pooler/direct connection choice, password URL encoding, SSL mode, and Supabase network restrictions.
- **API is unhealthy:** inspect `docker compose logs --tail 150 registry-api`; verify migrations are applied and schema matches the current code.
- **R2 upload fails:** check account ID, bucket name, endpoint, token permissions, and that the bucket is private.
- **Worker has no jobs:** confirm the upload created a job in the same Supabase database used by the worker.
- **Worker starts processing unexpected jobs:** stop it immediately with `docker compose stop registry-worker` and confirm the configured database is a sandbox project.
- **Core API cannot reach localhost:** use `host.docker.internal` from a separate Windows Docker container, or `registry-api` only when both services share a Compose network.

