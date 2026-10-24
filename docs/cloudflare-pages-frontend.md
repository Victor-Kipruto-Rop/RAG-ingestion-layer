# Deploy the Datasource Frontend with Cloudflare Pages

This repository's production frontend is intended to be served at:

- **Frontend:** `https://datasource.pesaguard.co.ke`
- **API:** `https://api.datasource.pesaguard.co.ke`

This guide configures the frontend for Cloudflare Pages. It does not create a Cloudflare project, change live DNS, deploy the app, or confirm either hostname is live.

## Cloudflare Pages project settings

Create a Pages project connected to this GitHub repository, `Victor-Kipruto-Rop/pesaguard-datasource`.

| Setting | Value |
|---|---|
| Production branch | The repository's approved release branch, verified from repository settings; do not assume the integration branch is approved for production |
| Root directory | `frontend` |
| Framework preset | Vite (or None if Vite is not offered) |
| Build command | `npm run build` |
| Build output directory | `dist` |
| Production environment variable | `VITE_API_BASE_URL=https://api.datasource.pesaguard.co.ke` |

Use the repository's approved production branch for real production releases. The integration branch is listed only so the initial configuration can be previewed; do not accidentally designate it as permanent production if your release branch is different.

Use `chore/local-pesaguard-integration-readiness` as a preview branch if needed, and promote only after review. The value of `VITE_API_BASE_URL` is a public API origin, not a secret. Vite embeds it in the browser bundle. **Never put datasource API keys, database credentials, signing secrets, or server-only tokens in any `VITE_*` variable.**

In Cloudflare Pages, add `VITE_API_BASE_URL` under **Settings → Environment variables → Production**. Set it to the exact HTTPS API origin above. Do not configure preview deployments to call production by default; use a separate staging API for previews, or leave previews unconfigured until a safe staging environment exists.

## Git-connected deployment

1. In Cloudflare Dashboard, open **Workers & Pages → Create → Pages → Connect to Git**.
2. Select `Victor-Kipruto-Rop/pesaguard-datasource`.
3. Set the root directory to `frontend`, build command to `npm run build`, and output directory to `dist`.
4. Set the production API variable as described above.
5. Deploy a preview first and verify the built app uses the expected API origin. Confirm the preview does not send requests to production unless explicitly intended.
6. After review, configure the actual approved production branch and trigger a production deployment.
7. Open the deployment URL and verify login, session/cookie behavior, API requests, and client-side route refreshes before attaching the production domain.

The repository includes `frontend/wrangler.jsonc` to declare the Pages project name and output directory for Wrangler-compatible workflows. If using Git integration, use the dashboard build settings as the source of truth and keep them consistent with this file.

## Attach the custom frontend domain

1. Open the Pages project in Cloudflare Dashboard.
2. Go to **Custom domains → Set up a custom domain**.
3. Enter `datasource.pesaguard.co.ke` and follow Cloudflare's verification and DNS instructions.
4. If the domain is not in the correct Cloudflare zone/account, resolve that first. Do not guess an A record or CNAME target and do not overwrite existing records manually.
5. Wait for Cloudflare to report the custom domain and TLS certificate as active.
6. Verify `https://datasource.pesaguard.co.ke` and test a direct refresh on a nested frontend route.

Prefer adding the custom domain from the Pages project so Cloudflare can validate the association and guide the required DNS record. Do not change unrelated records such as MX, SPF, DKIM, or DMARC.

## API prerequisites (separate from this frontend deployment)

The frontend and API are different origins. Before releasing, the API hosting must be configured separately for `api.datasource.pesaguard.co.ke` and must have a valid HTTPS certificate.

The API must allow browser requests from exactly `https://datasource.pesaguard.co.ke` where CORS is required. Do not use wildcard CORS with credentials. Verify preflight requests, allowed methods/headers, and credential behavior against the API's actual authentication implementation. If the dashboard uses cookie sessions, confirm cookies are Secure and compatible with the intended same-site cross-subdomain flow; do not blindly change cookie settings.

The frontend must never call the internal datasource API using a privileged service key. The API key must remain server-side. Frontend authentication and authorization must continue to be enforced by the backend.

## Production verification checklist

- [ ] Cloudflare Pages root directory is `frontend`.
- [ ] Production build command is `npm run build` and output directory is `dist`.
- [ ] Production `VITE_API_BASE_URL` is exactly `https://api.datasource.pesaguard.co.ke`.
- [ ] Build succeeds and no localhost API URL is embedded in the production bundle.
- [ ] No secret is present in frontend variables or generated assets.
- [ ] SPA fallback works for direct navigation and refresh on nested routes.
- [ ] Custom domain is active in Pages and HTTPS certificate is valid.
- [ ] API CORS allows the exact production frontend origin when required.
- [ ] Authentication, cookie/session behavior, and tenant isolation are verified against the API.
- [ ] API health/readiness and safe authenticated flows pass.
- [ ] Preview deployments do not unintentionally use production data or credentials.

Record each check as PASS, FAIL, BLOCKED, or NOT RUN. A successful Pages build does not prove API availability or production readiness.

## Rollback

Before changing the production branch or custom domain, record the current Pages project settings and last known-good deployment. If the release fails, use Cloudflare Pages to roll back to the previous known-good deployment and verify the frontend and API flow. Do not delete DNS records or alter API production settings as an improvised frontend rollback.
