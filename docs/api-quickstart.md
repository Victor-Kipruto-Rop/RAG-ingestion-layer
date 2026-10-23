# Datasource API Quickstart

## Environments and keys
Use separate deployments and keys. The server-side `PESAGUARD_DATASOURCE_ENVIRONMENT` setting is authoritative; do not attempt to select an environment with a request header. Keep production keys in trusted server-side secret storage. Never put a production or management credential in React, mobile code, or a `VITE_*` variable.

Managed key creation is currently operator-only because the service does not yet have customer login/organization roles. See [API key lifecycle](api-key-lifecycle.md).

## Registry lookup
```bash
curl -sS "$DATASOURCE_BASE_URL/api/v1/registry/lookup?reg_no=CPR-123456" \
  -H "X-API-Key: $DATASOURCE_API_KEY" \
  -H "X-Correlation-ID: demo-request-001"
```

A local registry match is imported evidence, not authoritative proof of legal status. A `not_found` response means no matching record was found in this dataset, not that the organization does not exist.

## Preview before ingestion
```bash
curl -sS -X POST "$DATASOURCE_BASE_URL/api/v1/ingestion/preview" \
  -H "X-API-Key: $DATASOURCE_API_KEY" \
  -F "file=@./authorized-registry-sample.csv"
```

Preview is non-persistent and limited to 5 MiB. It supports CSV/XLSX only; it does not create a job or validate the authority of the contents.

## Queue an import
```bash
curl -sS -X POST "$DATASOURCE_BASE_URL/api/v1/ingestion/uploads" \
  -H "X-API-Key: $DATASOURCE_API_KEY" \
  -H "X-Correlation-ID: import-2026-001" \
  -H "Idempotency-Key: import-2026-001" \
  -F "file=@./authorized-registry-sample.xlsx"
```

The API returns a job ID and queues processing. Poll `GET /api/v1/ingestion/jobs` for status. A failed CSV/XLSX job may be manually requeued with `POST /api/v1/ingestion/jobs/{job_id}/retry`; the endpoint preserves committed row progress and does not retry PDFs.

## Common error handling
- `401`: missing/invalid credentials. Do not retry blindly; check secret configuration.
- `403 API_KEY_ENVIRONMENT_MISMATCH`: key belongs to a different environment. Use the matching sandbox/production key; do not change the environment header.
- `403 API_KEY_SCOPE_INSUFFICIENT`: issue a key with the required scope.
- `409 JOB_NOT_RETRYABLE`: the job state or file type is not eligible for retry.
- `413`: upload/preview limit exceeded.
- `422`: malformed file or invalid request.
- `429`: rate limit reached; respect `Retry-After`.
- `503`: required configuration or a dependency is unavailable; inspect readiness and correlation IDs.

## Verification cases
`GET /api/v1/verification/providers` lists provider readiness. BRS, KRA, and Peleza currently return `not_configured` until provider-specific adapters, approved access, and credentials are supplied. `POST /api/v1/verification/cases` records a case but does not perform a live verification while all providers are unconfigured.
