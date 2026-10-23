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
Registry lookup/search endpoints use a token bucket. When REDIS_URL is configured, buckets are shared across instances; otherwise the fallback is per-process and is not a distributed control. Set REDIS_URL to a managed Redis-compatible service only after approving its cost and availability. Cache entries are best-effort, use short negative TTLs, and are invalidated after committed ingestion updates. PostgreSQL remains authoritative.

## Metrics
Set METRICS_TOKEN to a strong secret to enable GET /metrics with the X-Metrics-Token header. Without a configured token the endpoint returns 404. Scrape over a restricted network path where possible. Histograms expose buckets for Prometheus-side p95/p99 calculations; they are not a guarantee that requests complete within a fixed latency.

## Production startup validation
Production startup validates a non-placeholder REGISTRY_API_KEYS, PostgreSQL DATABASE_URL, and the R2 account/access key/secret/bucket. If REQUIRE_HMAC is enabled, HMAC_SHARED_SECRET and REDIS_URL are mandatory. The application does not print configured secret values.