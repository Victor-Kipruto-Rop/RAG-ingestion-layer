# Local frontend and ingestion testing

The repository root `docker-compose.yml` starts the API, worker, Redis and Vite frontend as one local stack. The worker is essential: uploads create persisted jobs, and the worker claims queued jobs and processes them.

## 1. Prepare local configuration

From the repository root:
```powershell
Copy-Item .env.example .env
```

Before signing in, configure these local-only values in `.env`:
- `ADMIN_PASSWORD_HASH`: generate with the command below and paste the printed hash.
- `SESSION_SECRET`: a random value at least 32 characters long.
- `REGISTRY_API_KEYS`: replace the placeholder with a long random local-only service key. Never commit it.
- Keep `SESSION_COOKIE_SECURE=false` for plain HTTP localhost only.
- Keep `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`.

Generate a password hash after the Docker image can be built:
```powershell
docker compose build registry-api
docker compose run --rm registry-api python -m src.admin_auth hash-password
```

Copy the resulting hash into `ADMIN_PASSWORD_HASH`. Do not put the plaintext admin password in the environment file.

## 2. Start the connected stack
```powershell
docker compose up --build
```

Open:
- Frontend: http://localhost:5173
- API readiness: http://localhost:8000/health/ready
- API liveness: http://localhost:8000/health/live
- API documentation: http://localhost:8000/docs

The Compose stack uses a shared local SQLite file and local upload volume, plus a separate worker process. It is for development only, not production financial data.

## 3. Test ingestion
1. Sign in using the admin password whose hash is configured in `.env`.
2. Open **Data Sources** and register a source if you want source-specific metadata.
3. Open **Upload center** and submit a small, authorized CSV file.
4. Open **Ingestion Jobs**. The job should first appear as queued/processing and later show its persisted result. If it remains queued, inspect `docker compose logs -f registry-worker`.
5. Inspect API logs with `docker compose logs -f registry-api`.

The dashboard does not label the jobs page “Live” unless a real live-streaming feature exists. Refresh loads the persisted database state.

## 4. API key management is a separate identity flow

The **API Keys** panel calls the tenant-scoped `/api/v1/keys` endpoints. It requires a valid PesaGuard user access token with `sub` and `org_id` claims, plus the configured JWT secret/issuer/audience. The operator admin-password session is intentionally not treated as a tenant identity. For production, connect this panel to the real PesaGuard identity flow; do not put an internal registry service key in browser code.

## 5. Production caveats
- Configure a persistent PostgreSQL database, private object storage, strong service secrets and explicit CORS origins.
- Deploy a persistent worker using `backend/Dockerfile.worker` and command `python -m src.worker`. A web API service alone will create jobs but does not process them.
- Configure the Render custom domain and verify TLS before setting the frontend API URL to `https://api.datasource.pesaguard.co.ke`.
- Confirm database migrations have run before testing source management.