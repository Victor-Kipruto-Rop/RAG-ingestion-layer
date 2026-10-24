# GitLab CI/CD setup for PesaGuard Datasource

This guide configures GitLab as the CI/CD runner for the staging candidate while GitHub remains the current source repository. The pipeline is intentionally restricted to the branch `chore/production-ci-release-gates`; it does not deploy production.

## 1. Import the GitHub repository

1. In GitLab, choose **New project → Import project → GitHub**.
2. Authorize access to the GitHub account and import `Victor-Kipruto-Rop/pesaguard-datasource` as a **Private** project.
3. Confirm the branch `chore/production-ci-release-gates` and `.gitlab-ci.yml` are present.
4. Confirm the latest GitHub commit is included. A one-time import does not guarantee future commits will synchronize. If the branch is stale, synchronize it using your approved repository-mirroring workflow or push the branch to GitLab from a local clone.
5. Do not change the GitLab default branch or merge the staging candidate into a production branch as part of setup.

## 2. GitLab project settings

In **Settings → CI/CD**:

- Ensure CI/CD is enabled.
- Ensure at least one compatible GitLab Runner is available.
- Enable pipeline visibility only for project members.
- Protect the default/production branch if one exists, and protect release tags.
- Restrict who can change CI/CD variables and who can run deployment jobs.
- Require merge requests and successful pipelines for protected branches where supported by your plan.
- Set an appropriate job timeout and review GitLab usage/minute limits.

The current pipeline does not require a GitLab access token to run. GitLab Runner checks out the repository using its own job token.

## 3. Cloudflare Pages variables

Open **Settings → CI/CD → Variables** and add:

| Variable | Type | Guidance |
| --- | --- | --- |
| `CLOUDFLARE_API_TOKEN` | Variable, masked | Restricted token with only the required Cloudflare Pages permissions for the intended account. |
| `CLOUDFLARE_ACCOUNT_ID` | Variable | Account ID for the Cloudflare account hosting the staging Pages project. |
| `VITE_API_BASE_URL` | Variable | Actual staging API base URL. This is public frontend build configuration, not a secret. |

Set the Cloudflare token as **masked** and **hidden** if those options are available. Do not make the variables protected unless the staging branch is protected; protected variables are not available to unprotected branches. Do not use production API URLs or credentials for staging. Do not put database passwords, Supabase service-role keys, or signing secrets in any `VITE_*` variable.

The frontend build embeds `VITE_API_BASE_URL` at build time. Changing this variable requires a new frontend build and deployment.

## 4. Staging ingestion variables (only when required)

The two ingestion jobs are manual and require a dedicated staging database and staging-only object storage. Add the following only when you are ready to run staging ingestion:

- `DATABASE_URL`: staging PostgreSQL connection string.
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`
- `R2_ENDPOINT_URL`

Mask and hide credentials where supported. Never use production database or R2 credentials for these jobs. Limit who can start the jobs and access variables. The ingestion jobs can change data, so run them only against staging resources and a known test dataset.

## 5. Cloudflare Pages project

Create a Cloudflare Pages project named `pesaguard-datasource-staging` using Direct Upload if you want GitLab CI to deploy via Wrangler. If the project already exists, reuse it. Create a restricted Cloudflare API token scoped to the relevant account and Pages permissions. Store the token only in GitLab CI/CD variables.

The deployment job is manual and targets the Pages branch `staging`. The URL configured in the GitLab environment is a conventional preview URL; confirm the actual URL in Cloudflare before relying on it. The staging API must permit the exact deployed Cloudflare origin in its CORS configuration.

## 6. Pipeline jobs

- `backend-checks`: compile, lint, import checks, SQLite migrations, unit tests and Python dependency audit.
- `backend-postgres-tests`: PostgreSQL-backed test suite.
- `frontend-tests`: frontend tests, build and npm audit.
- `sdk-tests`: Python and JavaScript SDK tests.
- `staging-blueprint-validation`: structural checks of the staging Render blueprint.
- `docker-builds`: builds the API, worker and frontend container images.
- `cloudflare-pages-staging`: manual Cloudflare Pages deployment.
- `staging-ingestion-preflight`: manual non-destructive preflight using staging configuration.
- `staging-ingestion-batch`: manual bounded batch worker using staging-only database/storage credentials.

Merge-request pipelines run validation/test jobs. Deployment and ingestion jobs are limited to `chore/production-ci-release-gates` and require manual action.

## 7. First pipeline run

1. Open **Build → Pipelines**.
2. Run a pipeline for `chore/production-ci-release-gates`.
3. Fix any validation and test failures before deployment.
4. Confirm the Docker-in-Docker runner configuration supports the `docker-builds` job. If it does not, configure an approved runner with the required privileges or disable that job until a supported image builder is configured. Do not weaken the runner's security controls just to make the job pass.
5. Once the actual staging API is deployed and `VITE_API_BASE_URL` is set, run the manual `cloudflare-pages-staging` job.
6. Verify the deployed URL, API requests, CORS, login, tenant isolation and staging data behavior.

## 8. Supabase and database security

The CI pipeline does not provision Supabase, set database secrets, or prove tenant isolation. Before exposing staging, review all migrations and RLS policies, including the pending RLS lockdown work. Test both permitted and denied cross-tenant access. Never enable RLS blindly without appropriate policies, and never expose privileged database credentials to the frontend.

## 9. Repository synchronization

GitLab CI only runs commits that exist in GitLab. Importing from GitHub is not automatically a permanent two-way sync. Decide which repository is authoritative and document the process for bringing changes across. Avoid editing the same branch independently in both repositories. Do not store a GitHub token in CI unless an explicitly approved mirroring mechanism requires it.

## 10. Troubleshooting

- **No pipeline appears:** confirm `.gitlab-ci.yml` is at the repository root and the pipeline is running on `chore/production-ci-release-gates` or a merge request.
- **No runner available:** enable a compatible runner or configure a project/group runner.
- **Cloudflare token error:** check token scope, account ID and variable availability.
- **Missing API URL:** set `VITE_API_BASE_URL` to the real staging API and rebuild.
- **CORS failure:** add the exact Cloudflare staging origin to the staging API's allowed origins.
- **Docker build fails to connect:** the runner may not support Docker-in-Docker; use an approved compatible runner or image builder.
- **Ingestion job fails on missing variables:** configure staging-only database and R2 variables; do not substitute production credentials.
