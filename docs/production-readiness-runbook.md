# PesaGuard Datasource production-readiness runbook

## Safety boundaries

- Never run production ingestion merely to test connectivity.
- Never commit `.env`, database URLs, API keys, or R2 credentials.
- Keep the R2 bucket private. Worker credentials should be restricted to the required bucket and object-read operations; do not grant bucket administration or object deletion unless separately justified.
- Imported registry data is not automatically authoritative verification. Preserve source provenance and mark imported records unverified.
- PDF extraction is a preparation aid only. Never create or verify an organization automatically from extracted PDF text.

## Pre-deployment checklist

1. Confirm migrations 001 through 005 are applied to the intended Supabase project.
2. Confirm Render API health at `/health/live` and `/health/ready`.
3. Confirm production environment has `APP_ENV=production`, PostgreSQL `DATABASE_URL`, and the R2 variables. Do not copy production values into a local `.env`.
4. Confirm the R2 bucket is private and that the configured endpoint matches the account.
5. Confirm only intended operator services can enqueue ingestion jobs and the dashboard is not exposed without authentication.
6. Confirm an operational backup/restore procedure exists for PostgreSQL and retained raw objects.
7. Review Supabase security/performance advisors and resolve relevant findings before broad rollout.
8. Confirm alerts/owner are defined for worker failures, queue backlog, repeated retries, and storage/database outages.

## Production connectivity validation (non-destructive)

- For a manual GitHub Actions run, select `preflight` first. It checks database `SELECT 1` and private R2 bucket access without claiming jobs. `ingest` requires an explicit operator choice. Scheduled runs process bounded batches as configured.
- Call `GET /health/live` and `GET /health/ready` on the deployed API.
- Validate R2 connectivity with an approved, read-only object check using a known non-sensitive test object. Do not upload or delete production objects as an incidental test.
- Run a read-only database query such as `SELECT 1` using the worker's runtime configuration.
- Do not start the batch worker until credentials, access scopes, migration compatibility, and job-selection rules have been reviewed.
- Keep `REGISTRY_API_KEYS` out of the worker environment unless the worker explicitly needs it.

## Worker deployment decision

Use scheduled GitHub Actions only if the repository is eligible for hosted runner use and the workflow is not blocked by billing policy. Do not add a payment method to bypass a billing restriction. If hosted execution is unavailable, select a user-approved no-cost execution environment; do not assume a free VM has capacity or that a free tier permits continuous use.

For every batch run:
- Set a hard job limit and timeout.
- Prevent overlapping runs.
- Keep logs free of credentials, raw PDFs, tax PINs, and full organization payloads.
- Alert on repeated failed jobs and queue age.
- Confirm stale-job recovery and retry delays are bounded.

## Production smoke test

Only after the preceding checks pass, authorize one known, non-sensitive test dataset and job. Verify the job's status, inserted/updated/skipped counts, row errors, raw-import metadata, audit event, and expected source provenance. Do not use real customer data as a smoke-test fixture. Confirm retry behavior without deliberately corrupting production records.

## Incident recovery

1. Pause the worker schedule or stop the worker process.
2. Inspect job status, attempts, `next_attempt_at`, row errors, audit logs, and service logs.
3. Check database/storage availability and migration compatibility.
4. Requeue only jobs whose source object is still present and whose partial effects have been reviewed.
5. Record the incident, corrective action, and any data repair in an auditable change.

## PDF limitations

The worker can optionally OCR image-only PDFs when the Tesseract engine is installed and `PDF_OCR_ENABLED=true`. OCR is bounded to the first 25 pages by default and the extracted text is used only for diagnostics; it is not persisted as verified organization data and does not automatically populate organization records. Missing OCR dependencies, timeouts, encrypted files, oversized files, or uncertain extraction must remain in manual review. Every PDF remains in manual review; do not auto-approve registry facts from extracted text.
