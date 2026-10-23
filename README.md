# PesaGuard Registry Datasource

A standalone organization-data warehouse for PesaGuard. It imports authorized registry datasets, normalizes and searches organization records, preserves source provenance and change history, and exposes a protected internal API.

This is a datasource, not the PesaGuard customer onboarding system and not an authority that independently certifies companies. Imported data is marked unverified unless a trusted verification workflow establishes otherwise.

## Local development

1. Copy .env.example to .env; set a long random REGISTRY_API_KEYS secret.
2. For local smoke tests, SQLite is supported. For production, use Supabase PostgreSQL and private Cloudflare R2.
3. Create and activate a Python virtual environment.
4. Install backend dependencies: pip install -r backend/requirements.txt.
5. Start the API from the repository root: uvicorn src.main:app --app-dir backend --reload --port 8000.
6. In another terminal: cd frontend && npm install && npm run dev.
7. Tests: PYTHONPATH=backend pytest -q.

Do not commit .env, API keys, database URLs, or R2 credentials.

## Database migrations

Apply in order to PostgreSQL/Supabase:
1. database/migrations/001_initial.sql
2. database/migrations/002_provenance_and_versions.sql

Set APP_ENV=production only after migrations are applied. Production startup intentionally does not create tables automatically.

## PesaGuard service connection

Configure REGISTRY_API_KEYS on this service and the matching secret in the PesaGuard backend only. PesaGuard should call this service over HTTPS with X-API-Key. Never place this service key in React, a mobile application, or any browser-visible environment variable. Use a separate admin authentication mechanism for the dashboard.

Example request:

    GET /api/v1/registry/lookup?reg_no=CPR-123456
    X-API-Key: <server-side-secret>

The API returns found, a matching organization when present, source metadata, data-quality state, and timestamps. A local record is not proof of current legal status or authoritative KYB verification.

## Core endpoints

- GET /health/live
- GET /health/ready
- GET /api/v1/registry/lookup?reg_no=...
- GET /api/v1/registry/lookup?tax_pin=...
- GET /api/v1/registry/search?q=...
- GET /api/v1/organizations?page=1&page_size=25
- POST /api/v1/ingestion/uploads
- GET /api/v1/ingestion/jobs
- GET /api/v1/metrics/summary
- GET /api/v1/exports/organizations.csv

## Current limitations

- CSV import is synchronous and bounded; durable background workers and streaming uploads are required for large-scale ingestion.
- PDF uploads are tracked but PDF extraction/OCR and record import are not implemented.
- The React dashboard currently uses the internal API key in its browser request flow. Do not deploy that dashboard for production administration until a separate admin authentication layer is implemented. The PesaGuard-to-registry integration key must remain server-side.
- External government or commercial registry integrations are not activated.
- Run CI and production integration tests before relying on this service for live decisions.

See docs/ARCHITECTURE.md for the operating contract and scale roadmap.
