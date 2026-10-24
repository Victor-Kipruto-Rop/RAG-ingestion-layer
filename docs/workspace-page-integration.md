# Datasource workspace page integration

All dashboard endpoints below are protected by the datasource operator session cookie. The browser must not receive the registry service API key. State-changing operator requests use the in-memory CSRF token in `X-CSRF-Token`.

| Page | Backend endpoint(s) | Behavior / truth boundary |
| --- | --- | --- |
| Overview | `GET /api/v1/admin/workspace/metrics`, `/api/v1/admin/registry/overview`, `/api/v1/admin/ingestion/activity`, `/api/v1/admin/ingestion/jobs`, `/api/v1/admin/workspace/stream` | Persisted KPIs and jobs; SSE snapshots plus REST refresh fallback. Source catalogue entries are not represented as live integrations. |
| Data Sources | `GET/POST /api/v1/admin/sources`, `PATCH/DELETE /api/v1/admin/sources/{id}` | CRUD against the datasource registry source table; deletion is blocked when jobs reference the source. |
| Ingestion Jobs | `GET /api/v1/admin/ingestion/jobs` | Persisted job state only; no hard-coded “live” status. |
| Registry Records | `GET /api/v1/admin/organizations` | Persisted registry organizations with pagination and search. Tax PIN is masked by the API. |
| Upload Center | `POST /api/v1/admin/ingestion/uploads`, `/ingestion/uploads/presign`, `/ingestion/uploads/{job_id}/complete` | Authenticated uploads; large direct uploads require configured private object storage and bucket CORS. |
| API Keys | `GET/POST /api/v1/keys`, `POST /api/v1/keys/{id}/rotate`, `DELETE /api/v1/keys/{id}` | Requires a trusted PesaGuard user access token with organization claims. The operator cookie is not a customer identity token. |
| Data Quality | `GET /api/v1/admin/data-quality/overview` | Field presence and ingestion-row error counts from persisted records; not external KRA/BRS verification. |
| Warehouse | `GET /api/v1/admin/warehouse/overview` | Persisted raw import metadata, stored byte totals, warehouse access events and unresolved dead-letter rows. |
| Validation Rules | `GET /api/v1/admin/validation/rules` | Read-only application-defined checks. No user-editable rule table is present in this schema. |
| Audit Logs | `GET /api/v1/admin/audit/logs` | Persisted datasource audit events; sensitive audit detail values are not returned. |
| Settings | `GET /api/v1/admin/settings/overview` | Safe runtime configuration diagnostics. Secret values are never returned. |

## Local verification

1. Configure `backend/.env` with a local database, `SESSION_SECRET` (at least 32 characters), `ADMIN_PASSWORD_HASH`, explicit local CORS origin, and `SESSION_COOKIE_SECURE=false` for localhost only.
2. For distributed login rate limiting, start Redis and set `REDIS_URL`. Production refuses to enable password-protected dashboard sessions without Redis.
3. Set `frontend/.env` to `VITE_API_BASE_URL=http://localhost:8000`.
4. Run the repository's Docker Compose setup or run the backend and Vite frontend separately.
5. From `frontend/`, run `npm ci`, `npm test`, and `npm run build`.
6. From `backend/`, install `requirements-dev.txt` and run `pytest`.
7. Sign in, create a source, upload a small authorized CSV, and verify that a persisted job and registry rows appear across Overview, Jobs, Registry Records, Data Quality and Audit Logs.

Do not treat an enabled source catalogue entry as a successful external integration. Do not mark RLS as active until tenant identity and database policy enforcement are independently verified. Do not merge or deploy based only on a frontend render; the backend tests, frontend build, local ingestion flow, and production worker/storage configuration must all be verified.
