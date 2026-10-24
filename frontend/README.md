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

## Build and preview with Wrangler

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run build
npx --yes wrangler pages dev dist --config wrangler.jsonc
```

PowerShell example for a staging build:

```powershell
$env:VITE_API_BASE_URL = "https://YOUR-VERIFIED-STAGING-API-HOST"
npm ci
npm run build
npx --yes wrangler pages dev dist --config wrangler.jsonc
```

Replace the placeholder with the actual staging API URL only after the API has been deployed and verified. `VITE_API_BASE_URL` is compiled into browser JavaScript and is public; never put secrets in it.

## Deploy to Cloudflare Pages staging

The intended Pages project is `pesaguard-datasource-staging`. The GitLab job performs a manual deployment from the staging work branch.

Configure these GitLab CI/CD variables:

- `CLOUDFLARE_API_TOKEN`: least-privilege Pages deployment token; mask/hide it where supported.
- `CLOUDFLARE_ACCOUNT_ID`: Cloudflare account ID.
- `VITE_API_BASE_URL`: actual HTTPS staging API origin, not the production API and not the Supabase dashboard URL.

Then build and deploy from the repository root:

```bash
cd frontend
npm ci
npm run build
npm run pages:deploy:staging
```

The API origin must be configured in the build environment before `npm run build`. The backend must allow the exact Pages origin in CORS and must have the intended cookie/session settings. Do not deploy until the staging API URL and authentication flow have been verified.

## Routing and headers

- `public/_redirects` rewrites application routes to `index.html` so direct navigation and refresh work for React routes.
- `public/_headers` adds baseline browser security headers.
- `wrangler.jsonc` identifies the Pages project and build output directory.

Cloudflare Pages project creation, DNS/custom-domain configuration, CI variables, and successful deployment are separate operational steps; this configuration alone does not create or verify those resources.
