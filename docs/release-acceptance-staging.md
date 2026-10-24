# PesaGuard Datasource — staging release acceptance

**Status: BLOCKED — not approved for production deployment.**  
**Candidate:** PR #47, `feat/datasource-crud-jobs-api-keys`  
**Rule:** Never paste secrets, OTP values, access tokens, webhook signing secrets, database URLs, or SMTP credentials into GitHub issues, PRs, logs, or this document.

This checklist separates source-level review from checks that require real credentials and a deployed staging environment. A checkbox may only be marked complete after evidence is attached (redacted logs, test report, deployment IDs, or reviewer sign-off).

## 1. Current evidence and blockers

- The connected Render workspace lists one Datasource service: `pesaguard-datasource`, on branch `main`, at `https://pesaguard-datasource.onrender.com`. It is on the free plan, has no configured health-check path, and no separate Datasource staging/sandbox service or Key Value instance was identified.
- Render logs for deploy `dep-dbefg8k9v7es73cff15g` show the image built successfully but application startup failed at production configuration validation because `REDIS_URL` and PesaGuard identity signing configuration (or `DEVELOPER_ACCESS_TOKEN_SECRET`) were missing. The deploy ended `update_failed`; do not interpret a successful image build as a healthy deployment.
- The application source defines separate sandbox and production API base URL settings and key prefixes (`pg_sandbox_` and `pg_live_`). This source contract does not prove the deployed environment variables or DNS/TLS routing are correct.
- Google/GitHub OAuth and Resend/SMTP credentials were not provided in this request. Provider applications, verified sender identity, and live delivery therefore cannot be confirmed from source code alone.
- Latest inspected GitHub Actions run (`40121465378`, attempt 1) shows all five jobs failed within two seconds with `runner_id=0`, an empty runner name, and `steps=[]`; the job-log endpoint returns `BlobNotFound`. The prior run's second attempt behaved the same way. This indicates the jobs never reached a runner, so no test/build commands are evidenced as executed. The repository cannot diagnose whether runner provisioning is blocked by repository/account Actions settings or a GitHub-side issue; check Actions permissions/usage and GitHub Actions service health. This is **not** evidence that the source tests passed or failed.
- No production credentials were read or changed, no staging account was used, and no deployment was triggered.

## 2. Reproducible Render staging environment

A staging-only Blueprint is provided at `render.staging.yaml`. Select that exact Blueprint filename when creating a new Render Blueprint; do not apply it to the existing production service or sync it as a production Blueprint.

The blueprint defines a separate PostgreSQL database, private Key Value service, API web service, background worker, and frontend. It sets `APP_ENV=staging`, `API_ENVIRONMENT=sandbox`, the API readiness health check (`/health/ready`), database migrations, and `autoDeployTrigger: checksPass`. API and worker share staging-only secrets and staging storage credentials; the staging bucket must not be the production R2 bucket. Production API base URL remains a different hostname from the staging sandbox URL.

**Cost and access warning:** creating the Blueprint provisions Render resources and can incur charges. Review the selected plans and expected monthly cost before creating it. No cloud resources are created by committing this file. The Key Value service is configured without public inbound IP access; verify internal connectivity after creation.

During Blueprint creation, provide the prompted values through Render's secure setup flow:
- A password hash for the staging operator account (generate it with the documented `python -m src.admin_auth hash-password` command in a trusted local environment).
- A verified staging Resend sender/API key (or configure the documented SMTP alternative manually).
- Staging-only Cloudflare R2 account credentials and a dedicated staging bucket.
- The exact operator signup allowlist for staging, if operator signup is enabled.

Do not reuse production database credentials, R2 keys/bucket, mail credentials, or identity signing secrets. Optional Google/GitHub OAuth credentials must use staging callback URLs registered with each provider. The blueprint does not create DNS records or custom domains; it uses Render-managed service hostnames.

The worker now runs the same runtime configuration validation as the API before processing jobs. Staging is treated as production-like for required PostgreSQL, Redis, R2, HTTPS, signing-key, session, and fail-closed rate-limiting checks. The API readiness endpoint must remain unhealthy until database, object storage, and Redis are reachable.

## 3. Configure secrets in the deployment control plane

Set values through the authorized deployment provider's secret/environment-variable UI. Do not commit them to `.env.example`, source control, build args, or logs.

### Operator OAuth and transactional email

Required variables:
- `PUBLIC_BASE_URL` — canonical operator dashboard/API origin used to construct callback URLs.
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`.
- `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET`.
- `ADMIN_OAUTH_ALLOWED_EMAILS` — exact, lower-case operator addresses only; never use a public wildcard.
- Preferred: `RESEND_API_KEY` and `RESEND_FROM_EMAIL` on a verified Resend sending domain. Optional SMTP fallback: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_STARTTLS`, `SMTP_USE_SSL`.
- `AUTH_OTP_PEPPER` — independent high-entropy secret used to hash OTPs.
- `SESSION_SECRET` — independent high-entropy signing secret.
- `SESSION_COOKIE_SECURE=true` in HTTPS staging/production.
- `REDIS_URL` and PostgreSQL `DATABASE_URL` as required by production configuration.

Register exact OAuth callback URLs in provider consoles:
- `https://<operator-host>/api/v1/admin/oauth/google/callback`
- `https://<operator-host>/api/v1/admin/oauth/github/callback`

For the separate public developer account flow, configure provider callback URLs as returned by `GET /api/v1/developer/auth/oauth/providers` or the application's OAuth start/config endpoints. Do not reuse the internal operator allowlist or operator session secret for developer accounts.

### Developer platform and environment isolation

Use separate deployment services and independent secret sets for sandbox and production. Set `API_ENVIRONMENT=sandbox` only on the sandbox service and `API_ENVIRONMENT=production` only on production. Ensure each service uses its own environment-appropriate database/Redis/storage credentials and a distinct, strong `DEVELOPER_ACCESS_TOKEN_SECRET`. Keep identity issuer/audience and signing-key rotation configuration aligned with the trusted PesaGuard identity service.

Expected public host contract:
- Sandbox base URL: `https://sandbox-api.pesaguard.co.ke`
- Production base URL: `https://api.pesaguard.co.ke`
- Sandbox key prefix: `pg_sandbox_`
- Production key prefix: `pg_live_`

These are expected values from application configuration, not verified evidence of live DNS, TLS, host routing, or deployed environment settings.

## 4. Acceptance tests — staging only

Record a run ID, date, tester, deployed commit SHA, service IDs, and redacted evidence for every check.

### OAuth and transactional email
- [ ] `GET /api/v1/admin/oauth/providers` advertises only providers with client ID, client secret, and an explicit allowlist configured.
- [ ] Google sign-in completes authorization-code exchange, validates verified email, validates state, and only admits an allowlisted operator.
- [ ] GitHub sign-in obtains the primary verified email and only admits an allowlisted operator.
- [ ] Missing, incorrect, expired, and replayed OAuth state is rejected; provider errors do not create a session.
- [ ] Resend test mail is delivered to an approved staging mailbox using a verified sender domain; if SMTP fallback is intentionally used, verify TLS settings. Confirm sender authentication (SPF/DKIM/DMARC as applicable); redact OTPs and credentials.
- [ ] Signup OTP expires, cannot be reused, and is locked after the configured failed-attempt threshold.
- [ ] Password-reset requests return a generic response for both known and unknown addresses. Reset OTP expires and is single-use.
- [ ] Password reset revokes every active session for that account.

### Sandbox/production isolation and API keys
- [ ] Public platform config reports distinct sandbox and production base URLs.
- [ ] Sandbox service reports `API_ENVIRONMENT=sandbox`; production service reports `API_ENVIRONMENT=production` (verify through authorized runtime configuration inspection, not by exposing secret values).
- [ ] A sandbox key succeeds only against sandbox and is rejected against production; a production key succeeds only against production and is rejected against sandbox.
- [ ] Production key issuance is denied before production-access approval, for unverified organizations, and for non-owner/admin roles.
- [ ] An eligible workspace can submit one production-access request; duplicate pending requests are rejected; an authorized reviewer approves or rejects it with an audit event.
- [ ] Production keys have expiry, least-privilege scopes, one-time secret display, rotation/revocation behavior, and auditable lifecycle events.
- [ ] Revoked/expired keys fail on the next request; authorization cannot be bypassed by changing headers, request body, environment labels, or URL path.

### Webhooks and sessions
- [ ] Create a webhook to an approved staging receiver; reject non-HTTPS public destinations and private/loopback/link-local IPs.
- [ ] Send a test event and verify signature validation, event ID, timestamp/replay protection, response handling, and persisted delivery result.
- [ ] Verify retry behavior and delivery history for receiver timeout, 4xx, and 5xx responses. Confirm secrets and sensitive payloads are redacted from logs.
- [x] Source-level guard: webhook delivery history omits receiver response bodies and stores only HTTP status metadata; regression test added. Staging behavior still requires CI and runtime verification.
- [ ] List active sessions, revoke a different session, and prove its next authenticated request fails.
- [ ] Revoke the current session and prove the session cookie is cleared and subsequent requests fail.
- [ ] Confirm cookie flags, CSRF checks for unsafe requests, expiry enforcement, and Redis-backed distributed login throttling.

## 5. CI, database, and deployment gates

- [ ] Restore actionable GitHub Actions runners; require backend, PostgreSQL, frontend, SDK, and Docker/Compose checks to finish with green conclusions.
- [ ] Run Alembic migrations against a disposable PostgreSQL database and confirm tenant-isolation/RLS checks pass.
- [ ] Run the SDK suites for JavaScript and Python; verify sandbox/production URL and key-format enforcement.
- [ ] Deploy to a dedicated staging service only after CI is green; confirm the deployed SHA matches the reviewed candidate.
- [ ] Run smoke tests and the acceptance checks above against staging, not production.
- [ ] Confirm monitoring, alert routing, rollback plan, backups, and restore test evidence.

## 6. Release decision

Release status must remain **BLOCKED** until all mandatory staging checks have evidence, CI is green, sandbox and production services are demonstrably isolated, and an authorized reviewer approves the exact commit SHA. Do not deploy to production merely because OAuth buttons render or environment variables exist.

### Evidence record

- Candidate commit SHA:
- Staging service ID / URL:
- Sandbox service ID / URL:
- Production service ID / URL:
- CI run URL and conclusion:
- OAuth test report (secrets redacted):
- SMTP delivery evidence (OTP redacted):
- API-key/environment isolation report:
- Production-access approval/audit report:
- Webhook delivery report:
- Session-revocation report:
- Reviewer / approval timestamp:
- Final decision: **BLOCKED / APPROVED**
