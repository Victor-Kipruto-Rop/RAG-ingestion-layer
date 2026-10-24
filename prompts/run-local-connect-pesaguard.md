# AI Execution Prompt: Run Datasource Locally, Generate `.env`, and Connect to PesaGuard

> **Purpose:** Give an AI coding agent a strict, executable workflow for starting the datasource locally, safely creating local environment files, connecting it to the PesaGuard backend, and proving the integration works.

## Mission

Execute and verify the local integration between:

- Datasource repository: `Victor-Kipruto-Rop/pesaguard-datasource`
- PesaGuard backend repository: `Victor-Kipruto-Rop/api.pesaguard`

Use the existing integration branches where available:

- Datasource: `chore/local-pesaguard-integration-readiness`
- Backend: `feat/local-datasource-registry-integration`

Inspect both checked-out repositories before making changes. Do not stop after writing documentation or proposing commands. Run the available commands, start the services, test the connection, diagnose failures, implement narrowly scoped fixes, and report evidence. The primary local environment is Windows PowerShell with Docker Desktop.

## Mandatory safety and change-control rules

1. Never invent a working API, environment variable, schema, organization ID, access token, registry record, or test result. Inspect source code and configuration first.
2. Never print, commit, upload, or log secret values, production credentials, real KRA PINs, real registration numbers, personal data, or customer records.
3. Create local `.env` files from tracked `.env.example` files only when absent. Preserve an existing local file and update only values required for this integration.
4. Confirm `.env` is ignored by Git before writing secrets. Never commit `.env`, generated secrets, database dumps, local state, uploaded documents, or real customer data.
5. Generate high-entropy, local-only secrets using a cryptographically secure random generator. Do not reuse production secrets.
6. The datasource API key must exist only in datasource server configuration and PesaGuard backend server configuration. Never put it in frontend variables, JavaScript bundles, browser storage, or client-side requests.
7. Never connect local development to production databases, production credentials, production customer records, or live government integrations.
8. Do not bypass authentication, authorization, tenant isolation, validation, rate limits, or security controls to make a test pass.
9. A registry lookup is evidence-only. It must not verify, approve, reject, activate, or mutate an organization's verification status.
10. Do not rewrite working components or change unrelated behavior. Make the smallest safe changes, preserve user work, and explain each required change.
11. Do not alter production DNS, production deployments, live services, or production environment variables.
12. If Docker, repository access, credentials, or another dependency is unavailable, document the blocker and continue with independent checks.
13. Do not claim success unless the relevant command/test actually ran and passed. Separate passed, failed, skipped, and blocked checks in the final report.

## Phase 1 — Inspect both repositories

1. Confirm repository roots, current branches, working-tree status, latest commits, and any uncommitted changes. Preserve existing user changes.
2. Read the datasource `README.md`, `.gitignore`, `.env.example`, `docker-compose.windows.local.yml`, `backend/Dockerfile`, local PowerShell scripts, smoke tests, and `docs/local-pesaguard-integration.md`.
3. Read the backend `README.md`, `.gitignore`, `.env.example`, Compose configuration, startup entry point, datasource client/routes, authentication and tenant implementation, organization models, migrations, tests, and `docs/integrations/LOCAL_DATASOURCE_REGISTRY.md`.
4. Establish actual service ports, container names, networks, health checks, required variables, API-key header, request/response contract, and supported startup commands.
5. Confirm the backend route is registered and its session factory/model assumptions match the actual application.
6. Confirm the datasource endpoint and client agree on the lookup request and response schema. Do not change the API contract based on guesses.
7. Check port conflicts before starting anything. If both services need host port 8000, keep the datasource's internal port unchanged and publish it on an available host port, preferably 8010. Update all affected local configuration and documentation consistently.
8. Use Git status and diffs before and after edits; do not discard unrelated changes.

## Phase 2 — Generate local environment files safely

1. Create each repository's `.env` from its existing `.env.example` only if no `.env` exists. Do not overwrite an existing file wholesale.
2. Ensure `.env` is Git-ignored before adding any secret. Add an appropriate ignore rule if needed.
3. Generate a cryptographically secure, local-only datasource API key if one is not already configured. Use the exact same value in the datasource's `REGISTRY_API_KEYS` and the backend's `PESAGUARD_DATASOURCE_API_KEY`. Never print the value.
4. Configure local-only database, storage, sandbox/development environment, and localhost CORS settings according to the actual application. Keep cloud object-storage credentials empty unless the local stack demonstrably requires them.
5. Inspect backend configuration requirements before setting database URLs, JWT secrets, encryption keys, Redis URLs, or other mandatory variables. Generate independent local secrets in the exact format the application expects; do not copy production values.
6. Set the datasource base URL based on the actual network topology:
   - Backend running directly on Windows: use the datasource's published loopback port, e.g. `http://127.0.0.1:8010`.
   - Backend running in a container connecting through a host-published port: use `http://host.docker.internal:8010` if supported and allowlisted by the development client.
   - Both services on the same Docker network: prefer the datasource Compose service DNS name and internal container port.
7. Configure the client timeout variables using supported names and reasonable bounded values, typically a 2-second connect timeout and 5-second read timeout.
8. Only use local HTTP when the runtime is explicitly development/test and the hostname is allowlisted by the client. Do not weaken production HTTPS enforcement.
9. Keep all generated secrets out of terminal output, logs, screenshots, shell history where avoidable, test reports, and final summaries. Report only whether each required variable is configured.

## Phase 3 — Start and validate the datasource

1. Verify Docker CLI and Docker engine availability.
2. Validate the datasource Compose configuration before starting containers.
3. Use the repository's supported PowerShell script/Compose file to build and start the datasource API, worker, and frontend.
4. Check container status and health. Inspect relevant logs, ensuring secret values and sensitive data are redacted.
5. Verify the configured liveness and readiness endpoints, API documentation, and dashboard. Use the actual ports from the inspected Compose configuration.
6. Run the repository's datasource smoke test with the local API key supplied through an environment variable; never hard-code the secret in a committed script.
7. Test expected behavior for a valid local request, missing/invalid API key, malformed input, unavailable datasource, and readiness failure where practical.
8. Use only fictional test identifiers and seeded/imported local test records. If no matching record exists, report “no local matching record”; do not fabricate a successful registry match.
9. Do not claim the external BRS, KRA, Peleza, or any other government/vendor integration works unless that integration is configured and independently tested. Local datasource operation alone does not prove external connectivity.

## Phase 4 — Configure and start the PesaGuard backend

1. Install dependencies using the repository's documented environment and lock/requirements files; do not make broad dependency upgrades.
2. Configure the backend local environment with its own database, JWT, encryption, Redis, and other required development settings based on inspected code and Compose configuration.
3. Point `PESAGUARD_DATASOURCE_BASE_URL` at the reachable local datasource and set `PESAGUARD_DATASOURCE_API_KEY` to the same local-only key used by the datasource.
4. Confirm that the client uses bounded connection/read timeouts, safe error handling, correlation/request IDs where supported, response validation, and no secret leakage.
5. Run database migrations using the repository's established migration mechanism. Do not delete or reset an existing local database without explicit approval.
6. Start the backend using the repository's supported local workflow. Confirm the backend health/readiness endpoint and logs.
7. If the backend cannot start because of missing unrelated external dependencies, distinguish those blockers from datasource integration and do not disable security checks to work around them.

## Phase 5 — Verify the authenticated, tenant-scoped integration

The expected endpoint in the current integration design is:

`POST /api/v1/organizations/<organization_id>/registry-lookup`

Confirm the route and required permission in source before testing. The documented permission is `read:settings`; use the actual auth implementation as the source of truth.

1. Obtain a valid token for a local test user through the application's supported registration/login/bootstrap flow.
2. Create or use a local test organization through supported migrations, fixtures, or application workflows. Never bypass auth or manufacture an untrusted organization context.
3. Call the backend endpoint using a fictional registration identifier and a valid local bearer token. Do not call the datasource directly from browser code.
4. Confirm the backend sends the expected server-side request to the datasource and handles successful responses safely.
5. Verify the response is evidence-only, removes sensitive fields such as tax PINs and raw registry payloads from the browser-facing response where specified, and does not mutate verification status.
6. Verify missing/invalid authentication is rejected; a user cannot access an organization in another tenant; insufficient permission is rejected; invalid input is rejected; datasource timeout/unavailability and malformed responses produce safe errors.
7. Confirm correlation IDs and useful diagnostics are preserved without exposing credentials or sensitive registry data.
8. If the app's supported test fixtures cannot create a valid user/organization, document the exact missing setup and do not introduce a production auth bypass or fake successful result.

Example PowerShell call (adapt only after inspecting the actual route and local backend port):

```powershell
$base = 'http://127.0.0.1:<PESAGUARD_BACKEND_PORT>'
$organizationId = '<LOCAL_TEST_ORGANIZATION_ID>'
$token = '<TOKEN_FROM_LOCAL_LOGIN>'
$body = @{ registration_number = 'LOCAL-TEST-NOT-A-REAL-REGISTRATION' } | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "$base/api/v1/organizations/$organizationId/registry-lookup" `
  -Headers @{ Authorization = "Bearer $token" } `
  -ContentType 'application/json' `
  -Body $body
```

Do not run the example with literal placeholders. Use actual local test values only, and never paste the token into a committed file.

## Phase 6 — Tests and regression checks

Run the relevant checks available in the checked-out repositories. At minimum:

### Backend

```powershell
$env:PYTHONPATH = '.'
pytest -q pesaguard_backend_pipeline/tests/test_registry_datasource_client.py
python -m compileall -q pesaguard_backend_pipeline
```

Run route/authorization tests for the new endpoint and the repository's relevant test suite if practical. Use the actual project virtual environment and test commands if they differ.

### Datasource

- Validate Compose configuration.
- Run existing datasource unit/integration tests for the changed code.
- Run `scripts/test-pesaguard-local-integration.ps1` with the correct local API base URL and key supplied through environment variables.
- Check API readiness, authentication failures, request validation, and safe error handling.

### Integration/regression

- Confirm the backend can reach the datasource using the selected network URL.
- Confirm a valid authenticated lookup completes end to end against local datasource data.
- Confirm unauthorized and cross-tenant requests fail.
- Confirm verification status and organization approval state remain unchanged.
- Scan the diff for accidental secrets, `.env` files, test credentials, or local data.
- Do not claim CI is green unless current CI results have been checked. Investigate relevant failures; avoid unrelated refactoring.

## Phase 7 — Fix issues without scope creep

For each failure:

1. Capture the exact error with sensitive values redacted.
2. Identify whether the issue is environment setup, networking/port mapping, API contract, dependency installation, migration, authentication, tenant authorization, or application code.
3. Make the smallest justified change.
4. Add or update a regression test.
5. Re-run the failing check and the related integration checks.
6. Update documentation if the supported commands or ports changed.
7. Do not hide failures, skip required tests, disable auth, or replace real integration behavior with mocks merely to get a green result.

## Phase 8 — Documentation and Git hygiene

1. Ensure local setup instructions clearly describe prerequisites, how to configure local `.env` files, how to start/stop each service, actual local URLs, health checks, and the end-to-end test.
2. Keep tracked examples sanitized and use placeholders only in `.env.example`; never store generated local secrets there.
3. Check `.gitignore` and `git status --short` to verify local `.env` files and runtime data are not staged.
4. Review the final diff and confirm no production settings, unrelated files, or generated local artifacts are included.
5. Do not commit or push unless the user explicitly asks for a commit/push. If asked to commit, include only the intended prompt/code/docs and never secret files.

## Required completion checklist

- [ ] Both repository branches and working-tree changes inspected.
- [ ] Local environment files created or safely preserved.
- [ ] Local-only datasource API key generated/configured without printing it.
- [ ] `.env` files confirmed Git-ignored.
- [ ] Port/network configuration verified; any conflict resolved consistently.
- [ ] Datasource containers started and health endpoints checked.
- [ ] Datasource smoke tests executed.
- [ ] PesaGuard backend configured and started, or exact blocker documented.
- [ ] Backend datasource client tests and compile check executed.
- [ ] Authenticated end-to-end registry lookup tested, or exact missing prerequisite documented.
- [ ] Unauthorized, tenant-isolation, validation, and unavailable-datasource behavior checked.
- [ ] Verification status remains unchanged by lookup.
- [ ] Relevant logs reviewed without secret leakage.
- [ ] Final Git diff checked for secrets and unrelated changes.
- [ ] Documentation updated for any actual configuration changes.

## Final report format

Provide a concise, evidence-based report with:

1. **Result:** working end-to-end / partially working / blocked.
2. **Repositories and branches:** actual checked-out branch and commit for each.
3. **Local services:** service name, local URL/port, health status. Do not include secret values.
4. **Environment configuration:** list variable names configured and whether each is present; never show values.
5. **Integration proof:** actual endpoint tested, response outcome, and confirmation that tenant authorization and evidence-only behavior were respected.
6. **Tests:** exact commands and pass/fail/blocked status.
7. **Files changed:** paths and reasons.
8. **Remaining blockers:** exact error and actionable next step for each.
9. **Security check:** confirm no local `.env` or secret values were committed.

Do not describe a phase as complete unless its checklist items have been verified.