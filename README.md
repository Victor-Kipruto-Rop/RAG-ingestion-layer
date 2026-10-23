# PesaGuard Internal Registry System

FastAPI service for importing authorized corporate registry CSV datasets, normalizing company records, and providing authenticated internal lookups to PesaGuard. Local records are not authoritative KYB verification.

## Quick start
1. Copy `.env.example` to `.env` and set a long random `REGISTRY_API_KEYS` value.
2. Use PostgreSQL/Supabase in production; SQLite is supported for local smoke testing.
3. `python -m venv .venv` and activate it.
4. `pip install -r backend/requirements.txt`
5. `uvicorn src.main:app --app-dir backend --reload --port 8000`
6. `cd frontend && npm install && npm run dev`
7. Run tests with `pip install -r backend/requirements.txt && pytest -q` from the repository root after setting `PYTHONPATH=backend`.

Set `DATABASE_URL` to a SQLAlchemy PostgreSQL URL. Configure private R2 credentials to preserve original uploads. Never commit `.env` or production secrets. In production, apply `database/migrations/001_initial.sql` and set `APP_ENV=production`; the service intentionally does not auto-create production tables.

## API
- `GET /health/live` process liveness
- `GET /health/ready` database readiness
- `GET /api/v1/registry/lookup?reg_no=...` authenticated exact lookup
- `GET /api/v1/registry/search?q=...` authenticated search
- `GET /api/v1/organizations` authenticated paginated records
- `POST /api/v1/ingestion/uploads` authenticated CSV/PDF upload
- `GET /api/v1/ingestion/jobs` authenticated ingestion history
- `GET /api/v1/metrics/summary` authenticated dashboard metrics
- `GET /api/v1/exports/organizations.csv` authenticated CSV export

Pass `X-API-Key`. This first implementation imports CSV synchronously within bounded request limits; move large imports to a durable worker before high-volume production use. PDF upload is tracked but not yet imported into records. OCR and external provider fallback are not configured. Do not represent this implementation as complete authoritative KYB verification.
