# PesaGuard Developer Platform — operations and integration contract

## Environment isolation

Deploy two separately configured API environments; do not route sandbox and production hosts to one process configured for only one `API_ENVIRONMENT`.

| Environment | API base URL | Required key prefix |
|---|---|---|
| Sandbox | `https://sandbox-api.pesaguard.co.ke` | `pg_sandbox_` |
| Production | `https://api.pesaguard.co.ke` | `pg_live_` |

Set `API_ENVIRONMENT=sandbox` on the sandbox deployment and `API_ENVIRONMENT=production` on the production deployment. The gateway validates key prefix, persisted key environment, active/revoked state, expiry, scope and tenant rate limit. A mismatch is rejected and recorded as a security event.

Production keys can only be created when the developer workspace is verified, production access is approved, and the caller is an owner/admin. Developers submit a request from the portal. Approval is not a substitute for workspace verification.

## Account lifecycle

Developer accounts are separate from internal operator accounts.

- `POST /api/v1/developer/auth/signup/request-otp` sends a one-time verification code.
- `POST /api/v1/developer/auth/signup/verify-otp` consumes a valid code and provisions the account, workspace and initial project.
- `POST /api/v1/developer/auth/login` verifies a password and creates a persisted server-side session.
- `GET /api/v1/developer/auth/session` validates the cookie and returns a short-lived API control-plane token.
- `POST /api/v1/developer/auth/logout` revokes the current persisted session.
- `POST /api/v1/developer/auth/password-reset/request-otp` requests recovery using a generic response to reduce account enumeration.
- `POST /api/v1/developer/auth/password-reset/confirm` consumes the OTP, changes the password and revokes all sessions.
- `GET /api/v1/developer/sessions` lists sessions; `DELETE /api/v1/developer/sessions/{session_id}` revokes a session.
- `GET/PUT /api/v1/developer/profile` reads and updates the display/workspace name.
- `GET /api/v1/developer/notifications` returns workspace-scoped persisted API-key, production-access and webhook-delivery activity.

Cookies are HttpOnly, CSRF protected and Secure in production. Passwords must be at least 12 characters. OTPs are hashed with `AUTH_OTP_PEPPER`, expire, have a bounded attempt count and are delivered by configured SMTP. Set strong `DEVELOPER_ACCESS_TOKEN_SECRET`, `SESSION_SECRET`, and `AUTH_OTP_PEPPER` values (at least 32 random characters each), plus SMTP settings. Signup and reset stay disabled when required configuration is missing.

## Google and GitHub sign-in

Register the exact callback URLs in each provider console:

- `{DEVELOPER_OAUTH_CALLBACK_BASE_URL}/api/v1/developer/auth/oauth/google/callback`
- `{DEVELOPER_OAUTH_CALLBACK_BASE_URL}/api/v1/developer/auth/oauth/github/callback`

Set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CLIENT_ID`, and `GITHUB_OAUTH_CLIENT_SECRET` as applicable. Use HTTPS origins in production, and set `DEVELOPER_FRONTEND_URL` to the developer portal origin. Google requires a verified Google email; GitHub requires a primary verified email. OAuth state is checked against a short-lived HttpOnly cookie. Provider credentials stay server-side.

## API keys and production review

- `GET/POST /api/v1/keys` list/create tenant keys.
- `POST /api/v1/keys/{key_id}/rotate` atomically replaces a key.
- `DELETE /api/v1/keys/{key_id}` revokes a key.
- `GET /api/v1/keys/audit/events` lists key-management audit records.
- `POST /api/v1/developer/production-access/request` submits the developer's review request.
- Internal operators use `GET /api/v1/admin/developer/production-access/requests` and `POST /api/v1/admin/developer/production-access/requests/{request_id}/review`.
- Internal operators use `POST /api/v1/admin/developer/workspaces/{workspace_id}/verification` to record a manual verification decision. An evidence reference is mandatory. Revoking verification also revokes active production keys.

API keys are displayed once. Store them in a server-side secret manager. Browser applications should call your own backend; never embed a production secret in JavaScript or a mobile binary.

## Webhooks

Create/manage endpoints at `/api/v1/developer/webhooks`; use `POST /{webhook_id}/test` for a test delivery and `GET /{webhook_id}/deliveries` for actual outcomes. Endpoint URLs must be HTTPS and resolve to public addresses. Redirects are disabled and endpoints are revalidated at delivery time.

Each delivery includes `PesaGuard-Event`, `PesaGuard-Delivery` and `PesaGuard-Signature: t=<unix>,v1=<hex>`. The HMAC-SHA256 message is the ASCII timestamp, a period, and the exact raw request body bytes. Verify the signature in constant time before parsing the body, enforce a short timestamp tolerance, and deduplicate delivery IDs. The signing secret is returned only at creation; encryption at rest requires `DEVELOPER_WEBHOOK_ENCRYPTION_KEY`.

Supported events include `api_key.created`, `api_key.revoked`, `api_key.rotated`, `webhook.test`, `registry.lookup.completed`, `data.source.updated`, `production_access.requested`, and `production_access.reviewed`. Events are queued only for subscribed endpoints owned by the corresponding workspace.

## SDKs and local verification

Python:

```bash
cd sdks/python
python -m pip install -e ".[test]"
pytest -q sdk_client_tests.py
```

JavaScript (Node.js 18+):

```bash
cd sdks/javascript
node --test test/client.test.js
```

Both source-controlled SDKs enforce key-prefix/environment matching, support registry search and exact lookup, and include webhook signature verification. The portal's browser-based API Explorer is sandbox-only; production checks must run from a trusted backend. The portal also provides starter examples for cURL, JavaScript, Python, PHP, Go, Java, Ruby and C#. These SDKs are not yet published to PyPI/npm.

## Scope

This is a developer integration platform and read-only registry API. It does not move money, originate payment transactions, independently certify government records, or expose internal ingestion and warehouse operations to customer keys.
