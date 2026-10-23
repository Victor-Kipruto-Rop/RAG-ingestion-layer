# Windows local worker testing

This guide runs the datasource API and ingestion worker locally on Windows with Docker Desktop. The local stack is intentionally isolated from production: it uses a shared SQLite database and local file storage, and the compose file explicitly disables Cloudflare R2 credentials. It does not connect to Supabase or process production jobs.

## Prerequisites

- Windows 10/11
- Git
- Docker Desktop running, with Linux containers enabled
- A copy of this repository

Check Docker from PowerShell:

```powershell
docker --version
docker compose version
docker info
```

If `docker info` fails, start Docker Desktop and wait until its engine is running.

## 1. Get the repository

If you have not cloned it yet:

```powershell
git clone https://github.com/Victor-Kipruto-Rop/pesaguard-datasource.git
Set-Location pesaguard-datasource
```

If it is already cloned, change directory to the repository root and run `git pull` to get the latest committed files.

## 2. Create a local environment file

```powershell
Copy-Item .env.example .env
notepad .env
```

In `.env`, replace the example `REGISTRY_API_KEYS` value with a long, random local-only secret. Keep the other R2 fields blank. Do not paste production `DATABASE_URL` or R2 credentials into this local setup. The Windows compose file overrides the database and storage settings anyway, but keeping production secrets out of `.env` avoids mistakes when using another compose file.

The repository's `.gitignore` excludes `.env`. Never commit it.

## 3. Validate and start the isolated stack

Run from the repository root in PowerShell:

```powershell
docker compose -f docker-compose.windows.local.yml config --quiet
docker compose -f docker-compose.windows.local.yml up -d --build
docker compose -f docker-compose.windows.local.yml ps
```

The API and worker share the same SQLite database volume and local-upload volume. The worker restarts automatically if it exits, as long as Docker Desktop is running. This is a local test setup, not a guarantee that Windows will stay awake or Docker Desktop will start after every reboot.

Open the local API documentation at http://localhost:8000/docs. The API port is bound to localhost only and is not exposed to your network.

## 4. Submit a harmless sample CSV

In the local API docs, find `POST /api/v1/ingestion/uploads` and click **Try it out**. For the `X-API-Key` header, use the local-only value from `REGISTRY_API_KEYS` in `.env`. Upload `samples/test-organizations.csv` and execute the request.

The API should return HTTP `202` and a `job_id`. The worker polls the shared local database and processes queued CSV jobs. It may finish before you open the jobs list.

Check `GET /api/v1/ingestion/jobs` in the same local docs page, using the same local API key. Confirm the sample job reaches `COMPLETED` and has processed records. Use `GET /api/v1/organizations` to inspect imported sample rows. These sample records are fictional and must not be treated as verified companies.

## 5. View logs and stop the stack

```powershell
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-api
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-worker
docker compose -f docker-compose.windows.local.yml down
```

The normal `down` command preserves the local database and upload volumes. To permanently delete only this local test database and local uploads, run:

```powershell
docker compose -f docker-compose.windows.local.yml down -v
```

**Warning:** `down -v` deletes the local test data.

## Troubleshooting

- **Docker daemon unavailable:** start Docker Desktop, wait for it to finish starting, then retry `docker info`.
- **Port 8000 is busy:** stop the other local service using port 8000 before starting this stack.
- **API key rejected:** check that `REGISTRY_API_KEYS` in `.env` is a non-placeholder value and restart with `docker compose -f docker-compose.windows.local.yml up -d --force-recreate`.
- **Worker is not processing:** inspect `docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-worker`; ensure the API is healthy and the upload returned a job ID.
- **PDF status:** PDF uploads are retained and marked `NEEDS_PDF_PROCESSING`; OCR/extraction is not implemented. Use the provided CSV for this test.

## Important boundaries

This guide validates local API-to-worker ingestion with local storage. It does not prove that production Supabase/R2 credentials work, and it does not process queued production jobs. Test production connectivity separately and deliberately, with read-only or least-privilege credentials where possible. Do not run a second worker against production while another worker may be active unless you intend concurrent job processing.
