# Windows local development and worker testing

This setup runs the **API, React dashboard, and ingestion worker** on Windows with Docker Desktop. It is deliberately isolated from production: the API and worker share a local SQLite database, files use local storage, and the Compose configuration explicitly blanks the Cloudflare R2 credentials. It does not connect to Supabase or process production jobs.

## Prerequisites

- Windows 10/11
- Git
- Docker Desktop using Linux containers and a running Docker engine
- Internet access the first time to download container images and install Python/frontend dependencies

Check in PowerShell:

```powershell
docker --version
docker compose version
docker info
```

If `docker info` fails, start Docker Desktop and wait until its engine is running.

## Quick start

From the repository root, run the guided startup helper. It creates `.env` from safe defaults if missing, opens Notepad, validates Compose, builds and starts the stack, waits for the API readiness endpoint and dashboard HTTP response, and prints logs if either service does not become ready:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-windows-local.ps1
```

When Notepad opens, replace `REGISTRY_API_KEYS` with a long, random **local-only** value, save, close Notepad and rerun the command. Leave all R2 fields blank. Do not put production Supabase URLs, database passwords, or R2 keys in this local `.env`.

You can also start manually:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose -f docker-compose.windows.local.yml config --quiet
docker compose -f docker-compose.windows.local.yml up -d --build
docker compose -f docker-compose.windows.local.yml ps
```

The execution-policy change applies only to the current PowerShell process. It does not change Windows' permanent policy.

## Local-only URLs

- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs
- API liveness: http://localhost:8000/health/live
- API readiness: http://localhost:8000/health/ready

Both ports are bound to localhost and are not exposed to your LAN. The dashboard's API-key field is for local development only. Enter the local-only key from `.env`; never enter a production API key in a browser.

## Test a CSV end to end

1. Open the dashboard at http://localhost:5173.
2. Enter the local-only `REGISTRY_API_KEYS` value and connect.
3. Open **Upload center** and upload `samples/test-organizations.csv`.
4. Open **Ingestion jobs** and refresh until the job reaches `COMPLETED`.
5. Open **Organizations** and confirm the two fictional sample records appear.

The same test can be run through Swagger at http://localhost:8000/docs: use the local key in the `X-API-Key` field, call `POST /api/v1/ingestion/uploads` with the sample CSV, and then check `GET /api/v1/ingestion/jobs`.

These sample records are fictional and must not be treated as real companies or as evidence of registry verification.

## Logs and shutdown

```powershell
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-api
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-worker
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-frontend
docker compose -f docker-compose.windows.local.yml down
```

You can also stop the stack with:

```powershell
.\scripts\stop-windows-local.ps1
```

Normal shutdown preserves the local database, uploads, and frontend dependency volume. To permanently delete all local test data and volumes, run:

```powershell
docker compose -f docker-compose.windows.local.yml down -v
```

**Warning:** `down -v` deletes the local SQLite database and local uploads.

## What works and what does not

- API, dashboard, CSV upload, queue persistence, and worker processing are intended to work locally.
- The API and worker share the same SQLite database and local file-storage volume.
- The worker automatically restarts if it exits, as long as Docker Desktop is running.
- PDF uploads are retained and marked `NEEDS_PDF_PROCESSING`. Bounded text extraction and optional OCR diagnostics exist, but every PDF remains unverified and requires manual review; extracted text does not automatically create organization records.
- This local setup does not test Supabase, Cloudflare R2, external registry APIs, or production deployment behavior.
- The dashboard currently accepts the API key in the browser. This is suitable only for a local developer preview, not for an internet-facing or shared production dashboard.
- Docker Desktop and Windows must remain running for the worker to process jobs.

## Troubleshooting

- **Docker daemon unavailable:** start Docker Desktop, wait for it to finish starting, then retry `docker info`.
- **Port 8000 or 5173 is busy:** stop the other local service using that port, then rerun the Compose command.
- **API readiness times out:** inspect `docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-api`.
- **API key rejected:** check that `REGISTRY_API_KEYS` in `.env` exactly matches the value entered in the dashboard, then recreate the API container using `docker compose -f docker-compose.windows.local.yml up -d --force-recreate registry-api`.
- **Worker is not processing:** inspect worker logs, ensure the upload returned a job ID, and verify that the job is `QUEUED` rather than already completed or marked `NEEDS_PDF_PROCESSING`.
- **Frontend has not started yet:** first install can take time while npm downloads packages; inspect frontend logs before restarting.
- **Compose config fails:** confirm that `.env` exists and was copied from `.env.example`, and run `docker compose -f docker-compose.windows.local.yml config` to view the configuration error.
