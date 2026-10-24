# Developer platform email authentication and Resend setup

PesaGuard Datasource uses Resend as its preferred transactional email provider for developer-account verification and password recovery. SMTP remains an explicit fallback for deployments that have not configured Resend.

## Required environment variables

Set these on the backend service's secret/configuration manager (not in frontend variables):

- `RESEND_API_KEY`: server-side Resend API key with permission to send email.
- `RESEND_FROM_EMAIL`: sender identity on a domain verified in Resend, for example `PesaGuard <no-reply@your-verified-domain.example>`.
- `AUTH_OTP_PEPPER`: independent random secret of at least 32 characters, used to HMAC OTP values before persistence.
- `DEVELOPER_ACCESS_TOKEN_SECRET`: independent random secret of at least 32 characters.
- `SESSION_SECRET`: independent random secret of at least 32 characters.
- `DEVELOPER_ACCESS_TOKEN_ISSUER` and `DEVELOPER_ACCESS_TOKEN_AUDIENCE`: match the configured identity contract.
- `DEVELOPER_SESSION_TTL_SECONDS`: persisted session lifetime (default 30 days).

Use the Resend dashboard to verify the sending domain and configure its DNS records before attempting delivery. Do not commit provider keys to Git or expose them in `VITE_*` variables. Rotate keys if they may have been exposed.

SMTP variables are only used when the Resend API key/from-address pair is not configured. When Resend is selected and returns an error, delivery fails visibly; the service does not silently fall back to SMTP.

## Authentication routes

- `GET /api/v1/developer/auth/config` — reports whether sign-up, password recovery, and social sign-in are configured.
- `POST /api/v1/developer/auth/signup/request-otp` — requests a verification code; response text avoids confirming whether an account exists.
- `POST /api/v1/developer/auth/signup/verify-otp` — validates the six-digit code and creates the account/workspace/session.
- `POST /api/v1/developer/auth/login` — verifies the password and creates a persisted session.
- `POST /api/v1/developer/auth/password-reset/request-otp` — requests a recovery code with an account-enumeration-safe response.
- `POST /api/v1/developer/auth/password-reset/confirm` — consumes the code, changes the password, and revokes every active session for that account.
- `GET /api/v1/developer/auth/session` — verifies the HttpOnly cookie against the persisted session and issues a short-lived control-plane access token.
- `POST /api/v1/developer/auth/logout` — revokes the current persisted session and clears the cookie.
- `GET /api/v1/developer/sessions` and `DELETE /api/v1/developer/sessions/{session_id}` — inspect and revoke sessions.

The browser session cookie is HttpOnly. State-changing cookie-authenticated requests require the CSRF token in `X-CSRF-Token`. OTPs expire, have an attempt limit, and are stored as keyed digests rather than plaintext. The API applies rate limits to authentication attempts. Keep HTTPS enabled in production.

## Google and GitHub OAuth

Configure provider applications and set `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CLIENT_ID`, and `GITHUB_OAUTH_CLIENT_SECRET` on the backend. Register the exact callback URLs returned by the deployed public API:

- `{DEVELOPER_OAUTH_CALLBACK_BASE_URL}/api/v1/developer/auth/oauth/google/callback`
- `{DEVELOPER_OAUTH_CALLBACK_BASE_URL}/api/v1/developer/auth/oauth/github/callback`

Set `DEVELOPER_FRONTEND_URL` to the developer portal origin. OAuth uses state cookies and only accepts verified provider email addresses. A successful OAuth identity creates or signs into a developer-platform account; it does not grant internal operator access or production API-key approval.

## Sandbox and production isolation

- Sandbox base URL: `DEVELOPER_PUBLIC_BASE_URL` (default `https://sandbox-api.pesaguard.co.ke`).
- Production base URL: `DEVELOPER_PRODUCTION_BASE_URL` (default `https://api.pesaguard.co.ke`).
- Sandbox credentials use the `pg_sandbox_` prefix.
- Production credentials use the `pg_live_` prefix and require a verified workspace plus explicit production-access approval.
- Configure the sandbox and production origins as separate deployments. The API environment configuration must match each deployment; changing the dashboard dropdown is not a substitute for server-side environment isolation.

## Release verification

Before enabling public registration in production:

1. Confirm the sending domain is verified and a real Resend delivery succeeds.
2. Test invalid, expired, reused, and over-attempted OTPs.
3. Verify duplicate sign-up and reset responses do not reveal whether an email exists.
4. Verify password reset revokes every persisted session and old access tokens are rejected.
5. Verify CSRF checks, cookie flags, HTTPS redirects, rate limits and OAuth state validation.
6. Run backend unit tests and PostgreSQL integration tests against the candidate commit.
7. Do not declare email authentication production-ready solely because environment variables are present.
