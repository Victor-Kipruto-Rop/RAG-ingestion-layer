# Operator account, OTP and session setup

This feature adds database-backed operator accounts alongside the existing environment-configured legacy operator password. Registration is **not open to arbitrary email addresses**: only exact addresses listed in `ADMIN_SIGNUP_ALLOWED_EMAILS` may register. Google/GitHub OAuth is separately restricted by `ADMIN_OAUTH_ALLOWED_EMAILS`.

## 1. Apply the database migration

Back up the database first, then from the backend directory with the deployment environment loaded:

```bash
alembic upgrade head
```

This applies revision `0008_operator_auth_sessions`, creating `admin_accounts`, `admin_auth_challenges`, and `admin_sessions`. Verify the current revision using `alembic current`. Do not use `Base.metadata.create_all()` as a production migration strategy.

## 2. Configure email OTP delivery

Set these values in the deployment's secret manager or protected environment configuration:

- `ADMIN_SIGNUP_ALLOWED_EMAILS`: comma-separated exact email addresses approved for internal operator access.
- `AUTH_OTP_PEPPER`: random secret with at least 32 characters; never reuse the session or OAuth secret.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`.
- `SMTP_USERNAME` and `SMTP_PASSWORD` if the SMTP relay requires authentication.
- `SMTP_USE_STARTTLS=true` for the usual port 587 setup, or `SMTP_USE_SSL=true` for an implicit-TLS relay (set STARTTLS to false in that case).
- `AUTH_OTP_TTL_SECONDS=600` and `AUTH_OTP_MAX_ATTEMPTS=5` unless a reviewed policy requires different values.

Generate independent secrets with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Do not put real secrets in this repository or in client-side environment variables.

The sign-up and password-reset screens stay hidden until the API reports that email delivery is configured. A successful registration also requires the address to be on the explicit allowlist. Password reset sends a generic response to reduce account enumeration and revokes the account's active sessions.

## 3. Configure OAuth providers (optional)

Register server-side OAuth applications with these exact callback URLs:

- Google: `https://YOUR_PUBLIC_HOST/api/v1/admin/oauth/google/callback`
- GitHub: `https://YOUR_PUBLIC_HOST/api/v1/admin/oauth/github/callback`

Configure `PUBLIC_BASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`, and `ADMIN_OAUTH_ALLOWED_EMAILS`. The allowlist is mandatory. Use HTTPS, keep client secrets server-side, and never allow arbitrary OAuth identities to become operators.

## 4. Session behavior

- Sessions use signed HttpOnly cookies and a persisted server-side session row with a unique ID.
- Authenticated unsafe requests require the CSRF token returned by sign-in, held in frontend memory and sent in `X-CSRF-Token`.
- The server checks persisted revocation state on authenticated requests.
- Logout revokes the current server-side session and clears the cookie.
- The Sessions page lists active sessions and lets an operator revoke an individual session.
- Password reset revokes all sessions belonging to that account.
- Production requires HTTPS and `SESSION_COOKIE_SECURE=true`; shared login throttling requires Redis.

## 5. Verification checklist

- [ ] Run `alembic upgrade head` against a disposable test database and verify revision 0008.
- [ ] Verify email arrives through the configured SMTP relay.
- [ ] Confirm OTP expiry, one-use behavior, and the failed-attempt limit.
- [ ] Confirm an address outside the signup allowlist cannot create an account.
- [ ] Verify reset codes cannot reset a different email's account.
- [ ] Confirm password reset revokes other sessions and the old password stops working.
- [ ] Confirm a revoked session is rejected by a protected endpoint.
- [ ] Test OAuth callback state validation, verified email, and allowlist denial for both providers.
- [ ] Run backend tests, frontend Vitest, frontend production build, PostgreSQL integration tests and staging smoke tests.

These workflows are implemented in code but must not be treated as runtime-verified until the checklist and CI pass against the target environment.
