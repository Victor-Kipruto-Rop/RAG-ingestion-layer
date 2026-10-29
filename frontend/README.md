# PesaGuard Datasource frontend

The frontend is a Vite + React single-page application. Cloudflare Pages serves the static production build; Wrangler is used for local Pages preview and staging deployments.

## Requirements

- Node.js 22 or later
- npm
- A Cloudflare account and a Cloudflare API token with permission to deploy Pages for the target account

## Local development

From the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Set `VITE_API_BASE_URL` in your local environment to the API origin you intend to use. Do not use production credentials in frontend environment variables.

## Build and verify Cloudflare Pages output

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run pages:build
npx --yes wrangler pages dev dist --config wrangler.jsonc
```

`npm run pages:build` builds the app and verifies that the output contains the app entry point, bundled assets, brand assets, SPA route fallback, and baseline security headers.

PowerShell example for a staging build:

```powershell
$env:VITE_API_BASE_URL = "https://YOUR-VERIFIED-STAGING-API-HOST"
npm ci
npm run pages:build
npx --yes wrangler pages dev dist --config wrangler.jsonc
```

Replace the placeholder with the actual staging API URL only after the API has been deployed and verified. `VITE_API_BASE_URL` is compiled into browser JavaScript and is public; never put secrets in it.

## Cloudflare Pages project settings

For Git-connected deployment, configure the Cloudflare Pages project as follows:

- **Root directory:** `frontend`
- **Build command:** `npm ci --no-audit --no-fund && npm run pages:build`
- **Build output directory:** `dist`
- **Production branch:** `main`
- **Environment variable:** `VITE_API_BASE_URL` set to the exact HTTPS API origin for that environment (for example, the verified production API origin for production, and the staging API origin for preview/staging builds).

Set build variables separately for production and preview/staging environments. Do not point a production frontend at a staging API or a preview frontend at production. The API must allow the deployed frontend origin in CORS and must configure credentialed requests and secure session cookies correctly. Because frontend and API are separate origins, confirm the backend cookie SameSite/Secure policy, CORS allowlist, CSRF checks, and OAuth redirect URLs before enabling sign-in.

Do not store Cloudflare tokens, database credentials, signing secrets, email provider keys, or any other secret in `VITE_*` variables. Vite embeds these values in public JavaScript.

## Deploy to Cloudflare Pages staging with Wrangler

The intended Pages project is `pesaguard-datasource-staging`.

Configure these CI/CD variables in the deployment environment:

- `CLOUDFLARE_API_TOKEN`: least-privilege Pages deployment token; mask/hide it where supported.
- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account ID.
- `VITE_API_BASE_URL`: actual HTTPS staging API origin, not the production API and not the Supabase dashboard URL.

Then build and deploy from the repository root:

```bash
cd frontend
npm ci
npm run pages:build
npm run pages:deploy:staging
```

The API origin must be configured in the build environment before `npm run pages:build`. The staging deploy script rejects production API hosts, localhost, placeholders, and non-HTTPS origins. The backend must allow the exact Pages origin in CORS and have the intended cookie/session settings. Do not deploy until the staging API URL and authentication flow have been verified.

## Routing and headers

- `public/_redirects` rewrites application routes to `index.html` so direct navigation and refresh work for React routes.
- `public/_headers` adds baseline browser security headers.
- `wrangler.jsonc` identifies the Pages project and build output directory.
- `scripts/verify-pages-build.mjs` checks the deployable output for required files and routing/security configuration.

Cloudflare Pages project creation, DNS/custom-domain configuration, CI variables, and successful deployment are separate operational steps; this configuration alone does not create or verify those resources.
