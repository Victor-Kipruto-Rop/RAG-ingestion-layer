# GitLab CI/CD setup and operations

This repository is imported from GitHub. The staging candidate branch is
`chore/production-ci-release-gates`. GitLab CI/CD is intended to validate this
branch and manually deploy the frontend to the Cloudflare Pages staging project.
Do not use these instructions to deploy production.

## 1. Import and keep the repository current

1. Import `Victor-Kipruto-Rop/pesaguard-datasource` from GitHub into a **private**
   GitLab project.
2. Confirm `.gitlab-ci.yml` is present at the repository root and the branch
   `chore/production-ci-release-gates` exists in GitLab.
3. If you imported before this file was added, sync the GitHub import or push
   the new commit to GitLab. Importing is not a guarantee that future commits
   will automatically sync.
4. Pick one source-of-truth workflow. Recommended: GitHub remains the code
   review/source repository and GitLab is a one-way CI mirror. Do not enable
   competing two-way pushes.
5. GitLab pipelines only run for `chore/production-ci-release-gates` by design.
   Update `.gitlab-ci.yml` deliberately before changing that branch policy.

## 2. Required GitLab project settings

- **Visibility:** Private.
- **Build → Pipelines:** enabled.
- **CI/CD → Runners:** enable an available GitLab runner for this project.
- **Repository → Branches:** after import/sync is working, protect
  `chore/production-ci-release-gates` according to your review policy. Ensure
  the account used for GitHub-to-GitLab synchronization can still update it.
- **Settings → CI/CD → Variables:** add variables listed below.
- **Build → Pipelines:** check the first pipeline and inspect job logs. Do not
  retry a deployment job until the build and security/test gates are understood.

GitLab shared runners and project quotas vary by account and may require
verification or billing details. If jobs remain pending, inspect runner
eligibility, minutes/quota and project CI/CD settings.

## 3. Variables and secrets

Add variables under **Settings → CI/CD → Variables**. Never commit secrets,
paste them into issues, or expose them in build logs.

### Cloudflare Pages deployment

| Key | Type | Environment scope | Required when |
| --- | --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | Variable, masked and hidden if supported | `staging` | Deploy job |
| `CLOUDFLARE_ACCOUNT_ID` | Variable, masked if supported | `staging` | Deploy job |
| `VITE_API_BASE_URL` | Variable (not secret) | `staging` | Frontend build/deploy |

Create a Cloudflare API token scoped to the correct account with the minimum
Cloudflare Pages edit permission needed to deploy. Use the real Account ID.
Set `VITE_API_BASE_URL` to the **actual deployed staging API origin/base URL**,
including any required API prefix expected by the frontend. Do not point staging
at `https://api.pesaguard.co.ke` or any other production service.

The staging API has to be deployed and tested before the final value is set.
Do not put database passwords, Supabase service-role keys, signing keys or
private API credentials in any `VITE_*` variable: Vite bundles these values
into browser-delivered assets.

### Staging ingestion operations (only if these manual jobs are needed)

Use staging-only resources and scope these variables to `staging`:

- `DATABASE_URL`: staging database connection string.
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY` (masked/hidden).
- `R2_BUCKET_NAME`
- `R2_ENDPOINT_URL`

Do not use the production database URL, production R2 bucket, production access
keys, or production API secrets. If staging object storage is not configured,
leave these variables absent and do not run `staging-ingestion-batch`.

For variables marked **Protected**, GitLab exposes them only to protected
branches/tags. Either protect the staging branch and ensure the sync identity
can update it, or leave the variables unprotected but tightly scope them to
`staging` and keep the project private. Prefer protected variables once branch
protection and mirroring have been verified.

## 4. What the pipeline runs

| Job | Purpose | Expected behavior |
| --- | --- | --- |
| `backend-checks` | Compile, lint, import checks, SQLite migration smoke test, Python tests and dependency audit | Automatic |
| `backend-postgres-tests` | PostgreSQL integration tests and migration/RLS-related checks | Automatic; requires working service networking |
| `frontend-tests` | npm install from lockfile, unit tests, production build and npm audit | Automatic |
| `sdk-tests` | Python and JavaScript SDK tests | Automatic |
| `staging-blueprint-validation` | Validates the staging Render blueprint and safety assumptions | Automatic |
| `docker-builds` | Builds API, worker and frontend container images without publishing them | Optional manual job; requires a runner that supports Docker-in-Docker/privileged service |
| `cloudflare-pages-staging` | Builds frontend with staging API URL and deploys `frontend/dist` to Pages branch `staging` | Manual |
| `staging-ingestion-preflight` | Non-destructive staging configuration preflight | Manual; requires staging database configuration |
| `staging-ingestion-batch` | Processes a bounded batch of eligible staging jobs | Manual; requires staging DB and staging R2 |

A successful CI pipeline does not mean the API or database has been deployed,
that a domain is verified, or that tenant isolation is proven. Complete the
release acceptance checks separately.

## 5. Cloudflare Pages setup and deployment

1. In Cloudflare, create a Pages project named
   `pesaguard-datasource-staging` using Direct Upload if it does not already
   exist. The CI job uses Wrangler to upload prebuilt assets.
2. Add the Cloudflare variables above in GitLab.
3. Set `VITE_API_BASE_URL` to the real staging API URL.
4. Run a pipeline on `chore/production-ci-release-gates`.
5. Wait for validation, test and build jobs to pass.
6. Manually start `cloudflare-pages-staging`.
7. Confirm the job succeeds and copy the actual deployment URL from Cloudflare.
8. Open the URL and check login, API calls, browser console, CORS and network
   failures. Do not assume the anticipated Pages URL is live until Cloudflare
   confirms it.

The pipeline uploads to the Pages branch `staging`; the GitLab branch that
triggers the pipeline remains `chore/production-ci-release-gates`.

## 6. Runners and Docker builds

The `docker-builds` job uses Docker-in-Docker. The selected runner must support
the Docker service and privileged mode required by its executor. If your
available runner does not support this, either enable an appropriate trusted
runner or disable that job until you have one. Do not add privileged mode to an
untrusted shared runner without understanding the isolation implications.

The API and worker are not deployed by the Cloudflare job. Their staging
deployment, secrets, health checks and database migrations must be configured
separately. The staging Render blueprint is a separate deployment option; do
not sync it blindly if you have decided to host the frontend on Cloudflare.

## 7. Safe use of ingestion jobs

Both ingestion jobs are manual and declare the GitLab `staging` environment.
Before running them:

1. Confirm `DATABASE_URL` points to the staging database.
2. Confirm every R2 variable points to a dedicated staging bucket.
3. Confirm the data source is authorized for import and any input is a test
   dataset suitable for staging.
4. Run `staging-ingestion-preflight` first.
5. Inspect the result, then run `staging-ingestion-batch` only if safe.
6. Verify job counts, retry/dead-letter behavior and audit events.

Never configure a scheduled batch until staging has passed these checks. The
previous GitHub scheduled workflow was not copied as an automatic production
schedule.

## 8. Supabase and data security release gate

The staging Supabase project previously reported 11 tables with Row Level
Security disabled. Do not expose browser access or treat the environment as
ready until access policies have been reviewed and tenant-isolation tests pass.
Enabling RLS without appropriate policies can break legitimate server access;
broad policies can expose data. Review the pending lockdown migration and
confirm the server uses least-privilege credentials.

## 9. Troubleshooting

- **No pipeline:** verify the branch name and that `.gitlab-ci.yml` is at the
  repository root on that branch.
- **Pipeline stuck/pending:** check runner availability, CI minutes/quotas and
  protected-branch eligibility for variables.
- **Missing Cloudflare variable:** check the exact key spelling and whether
  environment scope is `staging`; the deploy job must have that environment.
- **Cloudflare authentication failure:** verify the token is valid, scoped to
  the correct account and has Pages edit permission.
- **Project not found:** create `pesaguard-datasource-staging` in the same
  Cloudflare account referenced by `CLOUDFLARE_ACCOUNT_ID`.
- **Frontend builds but API calls fail:** verify the staging API is deployed,
  `VITE_API_BASE_URL` is correct, the API permits the actual Pages origin in
  CORS, and the API's health endpoint is healthy.
- **Docker job fails to start daemon:** use a compatible trusted runner or
  disable the Docker-in-Docker job until one is available.
- **Ingestion job exits for missing variables:** configure staging-only DB and
  R2 variables; do not copy production secrets to make the job pass.
- **npm/pip audit fails:** inspect the reported dependency and resolve or
  explicitly review it. Do not silence the audit just to make the pipeline green.

## 10. Release completion checklist

- [ ] GitHub import/sync contains the current staging branch and CI files.
- [ ] GitLab pipeline validates and test jobs pass.
- [ ] Cloudflare staging project exists and deployment succeeds.
- [ ] Staging API URL is real and does not point to production.
- [ ] Staging API and database are separate from production.
- [ ] CORS, authentication, API-key environment separation and tenant access are tested.
- [ ] Supabase RLS policies are reviewed and tested.
- [ ] Ingestion jobs use only staging DB and staging object storage.
- [ ] Production service configuration and data remain untouched.
