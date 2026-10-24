# Local development

Runs the API, the worker and the dashboard on your machine with SQLite and local file storage. Nothing here
connects to Supabase, R2 or any production service.

## Prerequisites

Python 3.12+, Node 22+. (Docker is optional; see the end of this page.)

## 1. Configure

The backend reads `.env` from the directory it is started in, so the file goes in `backend/`:

```bash
cp .env.example backend/.env
```

Edit `backend/.env`:

1. Set `REGISTRY_API_KEYS` to a random value, e.g. `openssl rand -hex 32`. Use this key for service calls (`X-API-Key` header).
2. To sign in to the dashboard, set a password hash and a session secret:

   ```bash
   cd backend
   python -m src.admin_auth hash-password        # prints pbkdf2_sha256$...
   openssl rand -hex 32                          # use as SESSION_SECRET (>= 32 characters)
   ```

   Put the hash in `.env` **inside single quotes** (it contains `$`, which Docker Compose and shells would otherwise expand):

   ```
   ADMIN_PASSWORD_HASH='pbkdf2_sha256$600000$...'
   SESSION_SECRET=<the random value>
   ```

   Leave `SESSION_COOKIE_SECURE=false` for plain-http local use. It must be `true` anywhere behind HTTPS.

## 2. Run the backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m alembic -c alembic.ini upgrade head            # create / upgrade the database
uvicorn src.main:app --port 8000                         # API on http://localhost:8000 (docs at /docs)
```

In a second terminal (same virtualenv, from `backend/`) start the worker, which processes uploaded files:

```bash
python -m src.worker                 # keeps running; use `python -m src.worker --batch` to process once and exit
```

## 3. Run the dashboard

```bash
cd frontend
npm ci
npm run dev                          # http://localhost:5173
```

Sign in with the admin password from step 1. Upload `samples/test-organizations.csv` from the Upload center,
then watch the job in Ingestion Jobs (the worker must be running).

## 4. Try the API directly

```bash
KEY=<your REGISTRY_API_KEYS value>
curl -H "X-API-Key: $KEY" -F "file=@samples/test-organizations.csv;type=text/csv" http://localhost:8000/api/v1/ingestion/uploads
curl -H "X-API-Key: $KEY" "http://localhost:8000/api/v1/registry/search?q=local%20test"
curl -H "X-API-Key: $KEY" http://localhost:8000/api/v1/exports/organizations.csv
```

## Tests

```bash
pip install -r backend/requirements-dev.txt
pytest -q                            # from the repository root; uses a throwaway SQLite database
(cd frontend && npm test)
```

To also run the suite and the SQL-migration / row-level-security checks against PostgreSQL, set
`TEST_DATABASE_URL` (an empty database with the `pg_trgm` extension) and `TEST_PG_ADMIN_URL` (a superuser
connection used to create throwaway databases), for example
`postgresql+psycopg://user:pass@localhost/dbname`.

## Docker (optional, less tested)

`docker compose up --build` starts the API, worker, Redis and the dev dashboard from the root `docker-compose.yml`
(this one reads `.env` from the repository root: `cp .env.example .env`). For Windows with Docker Desktop, follow
[`windows-local-worker.md`](windows-local-worker.md). The Compose files have not been run in CI-less review, so report anything that fails.

## Troubleshooting

- **Dashboard login returns 503:** `ADMIN_PASSWORD_HASH` or `SESSION_SECRET` is missing, or `.env` is not in `backend/`.
- **Dashboard login says invalid credentials after copying the hash:** the hash lost its `$` parts; quote it as above.
- **Uploads stay QUEUED:** the worker is not running.
- **CORS errors in the browser console:** add your dashboard origin to `CORS_ORIGINS` (explicit origins only, no `*`).
