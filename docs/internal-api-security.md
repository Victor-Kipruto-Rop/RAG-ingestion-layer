# Internal API Security and Operations

## Transitional authentication
The registry API accepts the existing X-API-Key during migration. HMAC signing is available for server-to-server callers; do not enable REQUIRE_HMAC until every caller has been updated and tested. HMAC does not replace HTTPS/TLS.

## HMAC request signature
Configure HMAC_SHARED_SECRET as a high-entropy server-side secret in both services, then set REQUIRE_HMAC=true only after a coordinated rollout. Never expose this value in browser code or logs.

Each signed request must send:
- X-Internal-Timestamp: Unix timestamp in seconds.
- X-Internal-Nonce: unique random value for this request.
- X-Internal-Signature: lowercase hexadecimal HMAC-SHA256.

Canonical message (UTF-8, newline-separated):
1. Exact timestamp string.
2. Nonce.
3. Uppercase HTTP method.
4. URL path, excluding scheme and host.
5. Raw query string, preserving exact ordering and encoding.
6. Lowercase hexadecimal SHA-256 of the exact request body bytes (empty-body SHA-256 for GET).

Compute HMAC-SHA256 over that canonical message using HMAC_SHARED_SECRET. Both callers must use the same canonicalization. Timestamps outside HMAC_CLOCK_SKEW_SECONDS are rejected and nonces are single-use for HMAC_NONCE_TTL_SECONDS.

REQUIRE_HMAC=true also requires REDIS_URL so replay protection is shared across API instances. If Redis-backed replay protection is unavailable, signed requests fail closed. When HMAC is optional, a process-local nonce fallback is only a migration aid, not distributed replay protection.

## Rate limiting and cache
Registry lookup/search and paginated organization enumeration use a token bucket. Customer API-key buckets are keyed by a one-way tenant digest, so creating multiple keys for the same organization does not multiply its lookup quota. When REDIS_URL is configured, buckets are shared across instances; otherwise the fallback is per-process and is not a distributed control. Production startup therefore requires REDIS_URL. Cache entries are best-effort, use short negative TTLs, and are invalidated after committed ingestion updates. PostgreSQL remains authoritative.

## Metrics
Set METRICS_TOKEN to a strong secret to enable GET /metrics with the X-Metrics-Token header. Without a configured token the endpoint returns 404. Scrape over a restricted network path where possible. Histograms expose buckets for Prometheus-side p95/p99 calculations; they are not a guarantee that requests complete within a fixed latency.

## Production startup validation
Production startup validates a non-placeholder REGISTRY_API_KEYS, PostgreSQL DATABASE_URL, the R2 account/access key/secret/bucket, and REDIS_URL for shared rate limiting and coordination. If REQUIRE_HMAC is enabled, HMAC_SHARED_SECRET is also mandatory. The application does not print configured secret values.
## Dashboard sessions

The dashboard does not hold the service API key. An operator signs in at `POST /api/v1/admin/login`
with the admin password (verified against `ADMIN_PASSWORD_HASH`, PBKDF2-SHA256). The server returns a signed,
HttpOnly, SameSite=Strict cookie (`pg_admin_session`) and a per-session CSRF token. Cookie-authenticated
unsafe requests must send that token in `X-CSRF-Token`; the browser keeps it in memory only.

- Generate the hash: `python -m src.admin_auth hash-password`. Set `SESSION_SECRET` to at least 32 random characters.
- Production requires `SESSION_COOKIE_SECURE=true`; `CORS_ORIGINS` must be explicit origins (never `*`).
- Sessions are stateless and expire after `SESSION_TTL_SECONDS` (default 8 hours); logout clears the cookie
  but cannot revoke a copied token early. Rotate `SESSION_SECRET` to invalidate all sessions.
- Login attempts are limited per client address per process. Put a shared rate limit at your edge for multi-instance deployments.
- Service-to-service callers keep using `X-API-Key` or HMAC signatures; HMAC bodies are size-bounded before verification.


## Health and readiness

- `GET /health/live` indicates that the API process can answer requests; it does not claim dependencies are available.
- `GET /health/ready` checks PostgreSQL and reports Redis/object-storage dependency state. In production it returns HTTP 503 unless PostgreSQL, Redis, and private R2 object storage are healthy. When HMAC replay protection is enabled outside production, Redis is also required for readiness.
- `GET /health` returns an overall healthy/degraded status with dependency names and safe state labels only. It does not return credentials, connection strings, or exception details.
- Readiness checks must be tested against the actual staging Redis/R2 permissions and transient failures before relying on them for deployment routing.
- `GET /metrics` remains separately protected by `X-Metrics-Token`; keep it off public ingress where possible.
