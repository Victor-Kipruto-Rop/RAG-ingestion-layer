# Local PesaGuard integration readiness

This guide verifies the datasource locally before connecting it to the PesaGuard backend. It does not deploy anything, touch production, or require real registry records.

## Scope and contract

- Run the datasource API, worker, and dashboard using the isolated Windows Compose stack.
- PesaGuard backend calls the datasource API server-to-server over localhost during local development.
- Send the internal datasource key in `X-API-Key`; keep it in the PesaGuard backend environment only.
- Use `POST /api/v1/registry/lookup` with JSON containing exactly one of `reg_no` or `tax_pin` for lookup. A missing record is a valid lookup outcome; it is not proof that a company does not exist.
- Treat imported data as unverified unless a separate authorized verification workflow establishes otherwise.
- Do not call ingestion endpoints from customer-facing PesaGuard flows. Ingestion is an internal operator capability.
- Never connect this local setup to production databases, production R2 buckets, or production credentials.

## 1. Start the isolated datasource

From this repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-windows-local.ps1
```

If the helper asks you to edit `.env`, set `REGISTRY_API_KEYS` to a long random local-only value and save it. Leave all R2 fields blank. The local Compose file forces SQLite and local file storage, binds ports to loopback, and does not use Supabase/R2.

Expected local services:
- API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health/live
- Readiness: http://localhost:8000/health/ready
- Dashboard: http://localhost:5173

Check the stack:

```powershell
docker compose -f docker-compose.windows.local.yml ps
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-api
docker compose -f docker-compose.windows.local.yml logs --tail 100 registry-worker
```

## 2. Run the datasource smoke test

Set the local key in the current PowerShell session without committing it:

```powershell
$env:PESAGUARD_DATASOURCE_API_KEY = '<the local-only REGISTRY_API_KEYS value>'
.\scripts\test-pesaguard-local-integration.ps1
```

The smoke test checks liveness, readiness, authenticated lookup, response shape, and the presence of a correlation ID where returned. It uses a deliberately fictional registration number and does not insert or modify records.

## 3. Connect the PesaGuard backend

Configure the PesaGuard backend environment (not frontend/Vite variables):

```dotenv
PESAGUARD_DATASOURCE_BASE_URL=http://host.docker.internal:8000
PESAGUARD_DATASOURCE_API_KEY=<same local-only datasource key>
```

Use `http://127.0.0.1:8000` instead of `host.docker.internal` when the PesaGuard backend runs directly on the same host outside Docker. If both services run in the same Docker Compose network, use the datasource service DNS name and container port (typically `http://registry-api:8000`) by joining the Compose networks; do not use `localhost` from inside a container to reach another container.

The PesaGuard backend should:
1. Call the datasource only from server-side code.
2. Use explicit connection and read timeouts.
3. Validate the response schema and handle 401/403, 404, 429, 5xx, timeouts, malformed JSON, and `found: false` distinctly.
4. Propagate a correlation ID and log it without logging API keys, tax PINs, or full sensitive payloads.
5. Store source/provenance and check timestamps with the verification case.
6. Never mark an organization verified solely because a local registry record was found.
7. Keep tenant authorization and final verification decisions in PesaGuard.
8. Avoid automatic retries for non-idempotent operations; lookup is read-only and can use bounded retries for transient failures.

## 4. Local acceptance criteria

Do not call local integration ready until all are true:

- [ ] Datasource liveness and readiness both return successfully.
- [ ] Lookup without a key is rejected.
- [ ] Lookup with the local key returns a valid response schema.
- [ ] A missing fictional record is handled as `found: false`, not as a verified/rejected organization.
- [ ] PesaGuard backend can reach the datasource using the correct host for its runtime.
- [ ] API key exists only in backend/server environment variables.
- [ ] PesaGuard UI never calls the datasource directly and never receives the internal key.
- [ ] Timeout, 401/403, 429, 5xx, and malformed response paths are tested.
- [ ] No production credentials, data, or storage are used.
- [ ] No claim of BRS/KRA live verification is made until authorized provider adapters are connected and tested.

## 5. Shutdown

```powershell
.\scripts\stop-windows-local.ps1
```

Normal shutdown preserves local test data. Only use `docker compose -f docker-compose.windows.local.yml down -v` if you intentionally want to delete the local database and upload volumes.
