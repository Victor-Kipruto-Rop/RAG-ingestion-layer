# Developer platform deployment and integration guide

This is a public developer platform for third-party applications and websites. It is not limited to an internal PesaGuard integration. The developer control plane manages developer accounts, workspaces, projects, environment-specific API keys, production-access requests, webhooks, notifications, sessions, SDK examples, and API testing.

## 1. Separate sandbox and production deployments

Configure and deploy separate API origins. Do not point both DNS names at the same unisolated runtime.

| Setting | Sandbox deployment | Production deployment |
|---|---|---|
| Public API origin | `https://sandbox-api.pesaguard.co.ke` | `https://api.pesaguard.co.ke` |
| `API_ENVIRONMENT` | `sandbox` | `production` |
| API key prefix | `pg_sandbox_` | `pg_live_` |
| Intended use | Development and test data | Approved live integrations |

Set `DEVELOPER_PUBLIC_BASE_URL` and `DEVELOPER_PRODUCTION_BASE_URL` to those public origins. Production startup validates HTTPS and rejects the same hostname being configured for both environments. API-key validation checks the key prefix and persisted key environment against the running API environment. A sandbox key sent to the production origin receives an environment-mismatch response.

## 2. Authentication configuration

Use strong, randomly generated values for `DEVELOPER_ACCESS_TOKEN_SECRET`, `SESSION_SECRET`, and `AUTH_OTP_PEPPER` (at least 32 characters each). Configure the transactional email provider using `RESEND_API_KEY` and a verified `RESEND_FROM_EMAIL`, or explicitly configured SMTP as the documented fallback.

Sign-up requires a verified six-digit email OTP. OTPs are short-lived, purpose-separated, attempt-limited, stored as digests, and sent through the backend email service. Password reset uses a separate OTP purpose and revokes all active developer sessions after a successful reset. Sessions are persisted, HttpOnly, CSRF-protected for state-changing cookie requests, and revocable. Short-lived developer bearer tokens are linked to a persisted session and rechecked by API-key management.

### Google and GitHub OAuth

Configure provider applications and server-side client secrets. Register these exact callback URLs with each provider:

- `https://YOUR_API_ORIGIN/api/v1/developer/auth/oauth/google/callback`
- `https://YOUR_API_ORIGIN/api/v1/developer/auth/oauth/github/callback`

Set `DEVELOPER_OAUTH_CALLBACK_BASE_URL` to the API origin and `DEVELOPER_FRONTEND_URL` to the developer portal origin. Production OAuth deliberately fails closed when the callback origin is missing or not HTTPS. Google sign-in requires a verified Google email; GitHub sign-in requires a primary verified email. Do not put OAuth client secrets in frontend variables.

Provider credentials, sender-domain verification, DNS, TLS and successful callback delivery must be tested in staging. OAuth cannot be considered operational merely because the buttons or callback routes exist.

## 3. Production API key lifecycle

1. Sign up and verify the account email.
2. Create sandbox keys and test the integration against the sandbox origin.
3. Submit a production-access request with the use case and expected volume.
4. Complete the required workspace/organization verification.
5. An authorized operator reviews the request and explicitly approves it with an audit note.
6. Only then can an eligible owner/admin create a `pg_live_` key with a bounded expiry.
7. Store live credentials in a server-side secret manager; rotate and revoke them through the portal when required.

The browser API Explorer is sandbox-only by design. Do not place production credentials in browser JavaScript, mobile app bundles, public repositories or client-side storage. Production testing should run from a trusted backend or CI secret store.

## 4. Webhooks

Webhook endpoints must be public HTTPS URLs; loopback, private/reserved IPs, credential-bearing URLs, and redirects are rejected. Delivery uses a timestamped `PesaGuard-Signature: t=<unix>,v1=<hex>` header over `timestamp + "." + exact raw body`, an explicit event name and a delivery identifier. Transient network errors, HTTP 408/425/429 and 5xx responses receive bounded retries. Delivery status is persisted for inspection.

Receiver guidance:
- Read the exact raw request bytes before JSON parsing.
- Verify the HMAC using the endpoint signing secret and a constant-time comparison.
- Reject stale timestamps and deduplicate `PesaGuard-Delivery` identifiers.
- Return a 2xx response quickly and process expensive work asynchronously.
- Never log the signing secret or unredacted sensitive payloads.

The Python and JavaScript SDK candidates include signature-verification helpers. Other language folders provide starter clients/examples and should be validated in each consuming project's CI.

## 5. SDKs and test workbench

The portal supports cURL, JavaScript, Python, PHP, Go, Java, Ruby and C# request examples. Python and JavaScript source packages include offline contract tests. They are not published to PyPI/npm yet.

Run tests from the repository root:

```bash
cd backend
python -m pytest
cd ../frontend
npm ci
npm test
npm run build
cd ../sdks/python
python -m pip install -e ".[test]"
pytest
cd ../javascript
npm test
```

Run the backend's PostgreSQL integration suite and container/Compose checks in the project's configured CI/staging environment. These commands are a checklist, not a claim that they have passed in the current environment.

## 6. Release gate

Before enabling production traffic, require all of the following evidence:
- Green backend, PostgreSQL integration, SDK and frontend test/build checks.
- Successful migration to the candidate schema and a tested rollback/restore procedure.
- Verified DNS/TLS and distinct sandbox/production runtime configuration.
- Delivered OTP and password-reset emails using a verified sender.
- Successful Google/GitHub OAuth round trips with state validation and verified email.
- Tests proving sandbox keys are rejected on production and production keys are not issued before approval.
- Successful signed webhook test, signature verification, bounded retry behavior and persisted delivery inspection.
- Session revocation and password-reset tests demonstrating existing tokens stop working.
- Staging load, monitoring, alerting and incident/rollback evidence.

Keep the release blocked if a workflow fails before its steps execute. A runner startup failure is not a passing test and does not establish a code-level test failure either.
