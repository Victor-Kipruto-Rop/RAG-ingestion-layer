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

When Notepad opens, replace `REGISTRY_API_KEYS` and `DATASOURCE_ADMIN_TOKEN` with separate long, random **local-only** values, save, close Notepad and rerun the command. Leave all R2 fields blank. Do not put production Supabase URLs, database passwords, or R2 keys in this local `.env`.

You can also start manually:

```powershell
Copy-Item example.env .env
notepad .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The execution-policy change applies only to the current PowerShell process. It does not change Windows' permanent policy.

The local Compose configuration passes `DATASOURCE_ADMIN_TOKEN` to the API only for operator key management. After startup, run `scripts/create-sandbox-key.ps1` to create and smoke-test a managed sandbox key. For the PesaGuard backend environment variables and client example, follow [`pesaguard-sandbox-integration.md`](pesaguard-sandbox-integration.md).

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

## Automated end-to-end smoke test

After the containers are healthy, run this from PowerShell at the repository root:

```powershell
.\scripts\test-local-stack.ps1
```

The script checks API readiness and API-key authentication, uploads the fictional CSV fixture, then polls the API until the background worker finishes processing it. It fails with worker logs if the job fails or times out. It writes only to the local Docker volumes.

## Logs and shutdown

```powershell
docker compose logs --tail 100 registry-api
docker compose logs --tail 100 registry-worker
docker compose logs --tail 100 registry-frontend
docker compose down
```

You can also stop the stack with:

```powershell
.\scripts\stop-windows-local.ps1
```

Normal shutdown preserves the local database, uploads, and frontend dependency volume. To permanently delete all local test data and volumes, run:

```powershell
docker compose down -v
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
- **API readiness times out:** inspect `docker compose logs --tail 100 registry-api`.
- **API key rejected:** check that `REGISTRY_API_KEYS` in `.env` exactly matches the value entered in the dashboard, then recreate the API container using `docker compose up -d --force-recreate registry-api`.
- **Worker is not processing:** inspect worker logs, ensure the upload returned a job ID, and verify that the job is `QUEUED` rather than already completed or marked `NEEDS_PDF_PROCESSING`.
- **Frontend has not started yet:** first install can take time while npm downloads packages; inspect frontend logs before restarting.
- **Compose config fails:** confirm that `.env` exists and was copied from `example.env`, and run `docker compose config` to view the configuration error.
