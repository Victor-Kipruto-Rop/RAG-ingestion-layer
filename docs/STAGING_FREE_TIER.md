# Free-tier staging profile

This profile is deliberately separate from `render.staging.yaml`. It is designed to avoid provisioning paid Render resources.

## Resources

- One Render web service on the `free` plan.
- Reuses the existing `pesaguard-datasource-staging-redis` Key Value instance (free, Oregon).
- Uses the existing Supabase project `pesaguard-datasource-staging` for PostgreSQL; its connection string must be entered as the API service's secret `DATABASE_URL`.
- Frontend remains on Cloudflare Pages; this profile does not create a duplicate Render static site.
- Does not create a Render PostgreSQL database, a worker, or any paid resources.

## Required manual configuration

After reviewing and syncing this Blueprint in Render, set the staging-only values for `DATABASE_URL`, admin operator settings, email delivery, and Cloudflare R2 storage in the staging API service. Do not reuse production credentials or storage. Keep auto-deploy disabled until the GitLab runner and release checks are verified.

## Limitations

- Render free web services spin down after 15 minutes without inbound traffic and can take about a minute to wake.
- The existing free Redis instance is in-memory only; restarts can lose queued jobs and rate-limit state.
- Render does not offer free background workers. Therefore, this profile cannot process asynchronous ingestion jobs end to end. Do not treat ingestion as operational until a worker is deliberately provisioned and its cost approved.
- Supabase staging has RLS enabled with browser-role table privileges revoked. The API must use a trusted server-side database connection; do not put database credentials in frontend variables.
- Free services are for staging/testing, not production. Render free Postgres expires after 30 days, which is why this profile reuses the existing Supabase staging database rather than creating another Render Postgres instance.
