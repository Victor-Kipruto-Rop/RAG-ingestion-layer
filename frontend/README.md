# PesaGuard Datasource frontend

The frontend is a Vite + React single-page application. Deploy the compiled static build with **Cloudflare Pages**. Do not use `npx wrangler deploy` for this frontend: that command deploys a Worker and can publish the source directory rather than the Vite build output.

## Domains and project separation

- **Production frontend:** `datasource.pesaguard.co.ke`
- **Production API:** `api.datasource.pesaguard.co.ke`
- **Staging Pages project:** `pesaguard-datasource-staging`
- **Production Pages project:** `pesaguard-datasource-web`
- **Existing Worker URL:** `pesaguard-datasource.kiprutovictor39.workers.dev` (separate from the Pages frontend)

The production Pages project name deliberately differs from the existing Worker name to avoid confusing the two deployment targets. Do not delete or repoint the existing Worker while setting up Pages.

## Requirements

- Node.js 22 or later
- npm
- A Cloudflare account and a least-privilege Cloudflare API token with permission to deploy Pages

## Local development

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Set `VITE_API_BASE_URL` to the API origin for the environment. Values prefixed with `VITE_` are compiled into public browser JavaScript; never put credentials or secrets in them.

## Build and verify Cloudflare Pages output

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run pages:build
npx --yes wrangler pages dev dist --config wrangler.jsonc
```

`npm run pages:build` builds the app and verifies that the output contains the app entry point, bundled assets, brand assets, SPA route fallback, and baseline security headers.

PowerShell staging example:

```powershell
$env:VITE_API_BASE_URL = "https://YOUR-VERIFIED-STAGING-API-HOST"
npm ci
npm run pages:build
npx --yes wrangler pages dev dist --config wrangler.jsonc
```

Replace the placeholder with the actual HTTPS staging API URL only after that API has been deployed and verified.

## Cloudflare Pages settings

For Git-connected Pages deployment, use:

- **Root directory:** `frontend`
- **Build command:** `npm ci --no-audit --no-fund && npm run pages:build`
- **Build output directory:** `dist`
- **Production branch:** `main`
- **Production build variable:** `VITE_API_BASE_URL=https://api.datasource.pesaguard.co.ke`
- **Preview/staging build variable:** the actual verified staging API origin, never the production API

Use these settings for a Pages project, not a Workers static-assets project. If Cloudflare currently shows the command `npx wrangler deploy` and an output directory of `frontend`, stop using that configuration for the frontend Pages deployment.

## Attach the production custom domain

Cloudflare account and DNS changes are account-specific and are not applied by Git commits. In the Cloudflare dashboard:

1. Open **Workers & Pages** and create/select the Pages project named `pesaguard-datasource-web`.
2. Confirm its build output is `dist` and its production branch is `main`.
3. Open **Custom domains** for that Pages project, choose **Set up a domain**, and enter `datasource.pesaguard.co.ke`.
4. If `pesaguard.co.ke` is an active zone in the same Cloudflare account, follow the Pages domain flow so Cloudflare can create/verify the required DNS record and issue TLS. Do not add a guessed CNAME target.
5. If DNS is hosted elsewhere, use the exact `*.pages.dev` target shown by the Pages project and follow Cloudflare's custom-domain verification instructions. Do not change nameservers or apex records just to add this subdomain unless you intend to move DNS hosting.
6. Wait until Cloudflare reports the custom domain as active and HTTPS is working before sending users to it.

The frontend domain and API domain are different hostnames. Keep the API DNS record pointing at the backend service; do not point `api.datasource.pesaguard.co.ke` at Pages. The API must allow `https://datasource.pesaguard.co.ke` in its CORS configuration and correctly support credentials, CSRF, and secure cookies. Update OAuth provider callback/redirect allowlists for the real production domain where required.

## Deploy to Cloudflare Pages staging

The staging project is `pesaguard-datasource-staging`. Configure CI variables:

- `CLOUDFLARE_API_TOKEN`: least-privilege Pages deployment token
- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account ID
- `VITE_API_BASE_URL`: real HTTPS staging API origin

Then run from `frontend`:

```bash
npm ci
npm run pages:build
npm run pages:deploy:staging
```

The staging script rejects production API hosts, localhost, placeholders, and non-HTTPS origins. Confirm the backend allows the exact staging Pages origin in CORS before testing authentication.

## Deploy production Pages

Only after the Pages project exists, the production API is verified, and the custom domain is attached, configure `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, and `VITE_API_BASE_URL=https://api.datasource.pesaguard.co.ke`. Run from `frontend`:

```bash
npm ci
npm run pages:deploy:production
```

The production script validates the exact production API origin, runs the Pages build and verification, then deploys the built `dist` directory to the `pesaguard-datasource-web` Pages project on `main`. It will fail rather than deploy if the API origin is missing or mismatched.

## Routing and security headers

- `public/_redirects` rewrites application routes to `index.html` so direct navigation and refresh work.
- `public/_headers` adds baseline browser security headers.
- `wrangler.jsonc` is for staging Pages; `wrangler.production.jsonc` is for production Pages.
- `scripts/verify-pages-build.mjs` checks the deployable output for required files, SPA fallback, and baseline headers.

A successful Wrangler command alone does not prove the site works. After deployment, test the homepage, nested-route refresh, browser console/network errors, API requests, signup/login/password reset, OAuth redirects, CORS, session cookies, and CSRF protections.
