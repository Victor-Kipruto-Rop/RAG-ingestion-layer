# PesaGuard Developer Platform

The public developer platform is the primary frontend at `/`. The legacy internal operations console remains available at `/internal`. Developer accounts are isolated from operator accounts and do not grant access to internal administration routes.

## Platform features

- Email sign-up with a six-digit, expiring OTP; passwords require at least 12 characters.
- Password reset with a time-limited OTP and revocation of every existing developer session.
- Google and GitHub OAuth authorization-code flows, provider-side verified email checks and state-cookie validation.
- HttpOnly session cookie, CSRF protection for state-changing cookie-authenticated requests, persisted sessions and session revocation.
- Tenant/workspace-partitioned API-key management, one-time secret display, scoped read access, rotation, revocation, expiry and audit events.
- Separate sandbox and production API origins and key formats.
- Production-access request workflow; live key creation remains blocked until authoritative workspace verification and production approval.
- HTTPS webhook registration, event subscriptions, signing secrets encrypted at rest, test delivery and persisted delivery history.
- API Explorer, SDK starter examples for cURL, JavaScript, Python, PHP, Go, Java, Ruby and C#, plus OpenAPI/Swagger/ReDoc links.

## Environment boundary

| Environment | Base URL | Key format |
|---|---|---|
| Sandbox | `https://sandbox-api.pesaguard.co.ke` | `pg_sandbox_...` |
| Production | `https://api.pesaguard.co.ke` | `pg_live_...` |

These hosts are configuration defaults, not a claim that DNS, TLS, routing or two deployments are already provisioned. Set `API_ENVIRONMENT=sandbox` on the sandbox deployment and `API_ENVIRONMENT=production` on the production deployment. The backend rejects a key whose declared environment does not match the deployment. Never route both origins to the same deployment.

## Required server configuration

Set these through the deployment secret manager. Never commit real values:

- `DATABASE_URL`: PostgreSQL in staging/production; migrations must be applied.
- `SESSION_SECRET`: at least 32 random bytes, for signed developer sessions.
- `DEVELOPER_ACCESS_TOKEN_SECRET`: separate random secret of at least 32 characters.
- `AUTH_OTP_PEPPER`: separate secret for OTP digests.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and credentials if authentication is required by the SMTP relay.
- `DEVELOPER_WEBHOOK_ENCRYPTION_KEY`: stable random value of at least 32 characters; back it up securely.
- `DEVELOPER_PUBLIC_BASE_URL`: public sandbox API origin.
- `DEVELOPER_PRODUCTION_BASE_URL`: public production API origin.
- `DEVELOPER_OAUTH_CALLBACK_BASE_URL`: public API origin receiving OAuth callbacks for this deployment.
- `DEVELOPER_FRONTEND_URL`: public frontend origin used after successful OAuth.
- `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`.
- `GITHUB_OAUTH_CLIENT_ID` / `GITHUB_OAUTH_CLIENT_SECRET`.
- `SESSION_COOKIE_SECURE=true` in production; local HTTP development may use false only in a non-production environment.
- `CORS_ORIGINS`: explicit frontend origins only. Wildcard origins are not allowed with credentials.
- `VITE_API_BASE_URL`: set to the intended API origin when the frontend is deployed separately; blank means same-origin in production.

Register these exact OAuth callback paths on the provider applications, using the API origin configured for the deployment:

- `/api/v1/developer/auth/oauth/google/callback`
- `/api/v1/developer/auth/oauth/github/callback`

Do not copy the sandbox callback to a production OAuth application unless the deployment intentionally shares the same callback host. Provider secrets must remain server-side.

## Key management API

The dashboard signs in with a persisted developer session, then receives a short-lived developer access token for the API-key control plane. That token is held in memory and sent as a Bearer token to `/api/v1/keys`. Refreshing the browser requires a fresh token from `/api/v1/developer/auth/session`; no long-lived access token is stored in local storage.

- `GET /api/v1/keys/me`: current identity and key eligibility.
- `GET /api/v1/keys`: keys belonging to the authenticated workspace.
- `POST /api/v1/keys`: create a sandbox key or, if approved and verified, a production key.
- `POST /api/v1/keys/{id}/rotate`: atomically revoke and issue a replacement.
- `DELETE /api/v1/keys/{id}`: revoke a key.
- `GET /api/v1/keys/audit/events`: workspace-scoped key audit events.
- `POST /api/v1/developer/production-access/request`: submit production use case and expected volume.

Customer API keys are restricted to documented read-only scopes. Internal ingestion, shared registry writes, warehouse operations and administrative endpoints are not granted to developer API keys.

## Webhooks

- `GET/POST /api/v1/developer/webhooks`
- `DELETE /api/v1/developer/webhooks/{id}`
- `POST /api/v1/developer/webhooks/{id}/test`
- `GET /api/v1/developer/webhooks/{id}/deliveries`

Use public HTTPS endpoints only. Verify the HMAC signature against the exact raw request bytes, compare in constant time, deduplicate event/delivery IDs, and return a 2xx quickly. Implement replay protection and idempotent handling on the receiving service. Webhook test delivery is asynchronous; a queued response does not mean the destination accepted it.

## API testing and SDK status

The API Explorer sends a real browser request to the selected configured origin. CORS, DNS, TLS and network failures are surfaced as failures, not replaced with sample responses. Use a backend test suite for CI acceptance because browser CORS behavior differs from server-side integration tests.

Language examples are starter snippets rather than published, versioned SDK packages. Do not advertise an SDK package as production-supported until it has a versioned release, compatibility policy, tests and a package registry release.

## Release gate

Before launch, run backend tests, PostgreSQL integration/migration checks, frontend tests and production build, OAuth provider callbacks, SMTP OTP flows, session revocation, key environment mismatch tests, webhook delivery tests, and browser smoke tests against both staging origins. Confirm TLS/DNS, CORS, database backups and restore, rate limits, alerting and deployment rollback. This code change alone does not prove any live provider credentials or infrastructure are configured.
