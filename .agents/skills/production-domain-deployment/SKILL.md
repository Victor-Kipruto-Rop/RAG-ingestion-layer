# Production Deployment and Domain Configuration

## Purpose

Use this skill when preparing, reviewing, or deploying the PesaGuard Datasource production frontend/API and their public domains.

- **Frontend:** `https://datasource.pesaguard.co.ke`
- **Backend API:** `https://api.datasource.pesaguard.co.ke`

These are the requested canonical production hostnames. Treat them as target configuration, not proof that DNS, TLS, hosting, or deployment is already configured.

## Non-negotiable safety gates

1. Start in read-only inspection mode. Identify repository, branch, commit, working-tree changes, hosting provider, deployment target, DNS provider, current DNS records, certificate status, and current production configuration.
2. Do not change live DNS, production environment variables, hosting configuration, secrets, firewall rules, access policy, databases, or deploy/restart production services unless the user explicitly authorizes that specific action.
3. Never infer a DNS target, IP address, CNAME destination, hosting service name, or TLS mode. Derive values from the actual hosting provider and existing deployment configuration. If unknown, stop and report the exact value needed.
4. Never expose secrets, API keys, bearer tokens, private keys, database URLs, or full environment dumps in output, logs, screenshots, commits, or browser bundles.
5. Preserve existing user changes and production availability. No destructive migrations, database resets, force pushes, or speculative DNS edits.
6. Do not report production-ready, live, secure, or healthy unless the relevant state was actually checked. Clearly distinguish CONFIGURED, VERIFIED, BLOCKED, and NOT CHECKED.
7. Local HTTP allowances must never leak into production. Production browser-to-API traffic must use HTTPS.
8. The browser must never receive the datasource API key used for backend-to-datasource or service-to-service authentication.

## Required domain contract

### Frontend

- Canonical origin: `https://datasource.pesaguard.co.ke`
- This is the browser-facing web application.
- Use the actual frontend build system's public API-base setting to target `https://api.datasource.pesaguard.co.ke`.
- Do not assume the variable name. Inspect the source/build configuration and verify the resulting production bundle.
- Configure exact-origin CORS only where needed by API/browser flows; do not use wildcard origins with credentials.
- Ensure redirects, canonical URLs, OAuth callback/allowed origins, cookie settings, CSP, and any service-worker configuration use the correct production origin.

### Backend API

- Canonical API origin: `https://api.datasource.pesaguard.co.ke`
- This serves API requests and documented health/readiness endpoints, as actually implemented.
- Validate host/origin handling, trusted proxy configuration, HTTPS enforcement, CORS allowlists, request size limits, timeouts, rate limits, security headers, and safe error responses.
- Do not expose interactive API documentation publicly unless that exposure is intentional and access/security review approves it.
- Keep provider credentials and datasource API keys in backend/server-side secret storage only.

## Mandatory implementation workflow

### 1. Inventory and baseline

- Inspect the current deployment manifests, Dockerfiles, frontend build configuration, backend settings, environment examples, health routes, CI/CD workflow, hosting configuration, and domain references.
- Record the branch, commit, dirty files, current production hostnames, and existing deployment state.
- Search for stale localhost URLs, wrong production hostnames, mixed-content references, hard-coded origins, wildcard CORS, and secrets.
- Do not change a file until its role and deployment impact are understood.

### 2. DNS and hosting plan

- Determine from the hosting provider whether each hostname requires a CNAME, A/AAAA record, or provider-managed alias. Do not guess record values.
- Confirm the DNS zone is authoritative and identify whether records are proxied or DNS-only, where relevant.
- Preserve unrelated records and existing mail-related DNS records.
- Verify domain ownership/verification requirements and certificate issuance prerequisites.
- Produce a proposed change table with hostname, record type, target/value, proxy mode, TTL, source of truth, and rollback before applying live changes.
- Applying DNS changes requires explicit authorization; a written plan alone does not change DNS.

### 3. Environment and frontend build

- Configure the production frontend API base to `https://api.datasource.pesaguard.co.ke` using the project's verified variable name.
- Verify no local URL or secret is embedded in the production build.
- Ensure API keys, signing secrets, database credentials, internal service URLs, and private tokens are not exposed through frontend-prefixed variables.
- Confirm production cookies use appropriate Secure, HttpOnly, and SameSite settings based on the actual authentication design; do not blindly change cross-site auth behavior.
- Confirm OAuth provider callback URLs and allowed origins match the actual auth flow before changing provider settings.

### 4. Backend security and availability

- Require HTTPS at the public edge and verify upstream/proxy behavior.
- Set CORS to the exact frontend origin when browser CORS is required. Add other origins only when justified by a documented product requirement.
- Validate trusted proxy settings and forwarded headers to prevent spoofed scheme/client IP.
- Verify authentication, authorization, tenant isolation, rate limiting, request validation, timeout handling, and redacted logging.
- Verify health and readiness endpoints do not disclose environment variables, internal credentials, PII, or detailed infrastructure secrets.
- Ensure a datasource registry lookup remains evidence-only and cannot automatically verify, approve, reject, activate, or mutate an organization.
- Confirm production database migrations have a reviewed backup/rollback plan and never reset production data.

### 5. Validation gates before release

Run the checks supported by the actual repository and record real results:

- Frontend production build and relevant tests.
- Backend tests, static checks, and configuration validation.
- Search built frontend artifacts for localhost URLs and secret-like values without printing any secrets found.
- DNS resolution for both canonical hostnames.
- TLS certificate validity, hostname coverage, chain, and expiry.
- HTTPS redirect and mixed-content checks.
- API readiness endpoint and a safe authenticated smoke test.
- Browser CORS preflight from the exact frontend origin.
- Invalid/missing auth and forbidden/cross-tenant access checks.
- Error/timeout behavior and rate-limit behavior where testable.
- No secrets or runtime artifacts in Git diff.
- Post-deployment smoke checks and monitoring/rollback criteria, only after deployment is explicitly authorized.

A DNS lookup, HTTP 200, or passing unit test alone does not prove the entire production system is ready.

### 6. Rollback and change control

- Before any authorized live change, record current values and prepare a reversible change plan.
- Define rollback triggers, owner/action, and verification commands before deployment.
- Make one bounded change at a time and verify it before proceeding.
- If health, TLS, CORS, auth, tenant isolation, or critical smoke checks fail, stop rollout and follow the approved rollback plan. Do not improvise destructive fixes.
- Do not merge, deploy, or modify live DNS unless explicitly requested and authorized.

## Completion report

Report:

1. Target hostnames: frontend `https://datasource.pesaguard.co.ke`, API `https://api.datasource.pesaguard.co.ke`.
2. Current verified DNS, TLS, hosting, and deployment state; mark unknowns NOT CHECKED.
3. Files/configuration changed and why.
4. Exact tests/commands and PASS, FAIL, BLOCKED, or NOT RUN status.
5. Security checks for CORS, HTTPS, secrets, auth, tenant isolation, and frontend bundle.
6. Proposed DNS records only when targets are verified from the hosting provider.
7. Rollback plan and remaining blockers.
8. State explicitly whether any live DNS/deployment changes were made.

## Cloudflare Pages frontend configuration

The datasource frontend is intended to run on Cloudflare Pages at `https://datasource.pesaguard.co.ke`.

- For the Pages project, use repository `Victor-Kipruto-Rop/pesaguard-datasource`, root directory `frontend`, build command `npm run build`, and output directory `dist`.
- Configure the public build-time variable `VITE_API_BASE_URL=https://api.datasource.pesaguard.co.ke` in the Production environment. This variable is visible to browser code by design and must contain no credential.
- Use the approved release branch as the Pages production branch. Use feature/integration branches for previews until explicitly approved.
- The repository's `frontend/wrangler.jsonc` declares the Pages project name and build output; keep Cloudflare dashboard settings consistent with it.
- `frontend/public/_redirects` supplies an SPA fallback for direct navigation and refreshes.
- Attach `datasource.pesaguard.co.ke` from the Pages project's Custom domains interface. Do not guess or manually overwrite DNS targets.
- The API remains a separate service at `https://api.datasource.pesaguard.co.ke`; API hosting, DNS, TLS, CORS, authentication, and tenant authorization require independent verification.
- Never put `REGISTRY_API_KEYS`, backend secrets, database credentials, or service-to-service tokens in `VITE_*` variables.
- Follow `docs/cloudflare-pages-frontend.md` for the setup and release checklist. Repository configuration alone does not create the Cloudflare project, attach a domain, deploy, or prove production health.

Live Cloudflare account changes, DNS edits, and production deployments require explicit authorization and must follow the existing safety gates.
