# GitHub Actions scheduled ingestion worker

This workflow is a low-cost alternative to a continuously running Render Background Worker. It runs every 15 minutes and can also be started manually from the Actions tab. Each run handles at most 10 eligible queued jobs, then exits.

## Required repository secrets

In **GitHub → repository → Settings → Secrets and variables → Actions**, add these repository or environment secrets:

- `DATABASE_URL`: the production PostgreSQL connection string used by the datasource service.
- `R2_ACCOUNT_ID`: Cloudflare account ID for R2.
- `R2_ACCESS_KEY_ID`: R2 API access key ID.
- `R2_SECRET_ACCESS_KEY`: R2 API secret access key.
- `R2_BUCKET_NAME`: `pesaguard-compliance-vault`.
- `R2_ENDPOINT_URL`: the account's R2 S3-compatible endpoint, `https://<account-id>.r2.cloudflarestorage.com`.

Use the same production database and R2 credentials that the API uses, but add them directly in GitHub Secrets. Never commit them to the repository, put them in workflow source, or print them in logs. Prefer a narrowly scoped R2 token with access only to the required bucket. Do not add `REGISTRY_API_KEYS` to this worker workflow; it connects directly to PostgreSQL and R2, not through the HTTP API.

## How it works

1. GitHub Actions starts the worker on a schedule or manual dispatch.
2. The worker attempts stale-job recovery and claims eligible `QUEUED` jobs using a database transaction and PostgreSQL row locking.
3. It processes up to 10 jobs and exits. A concurrency group prevents scheduled and manually dispatched runs from overlapping.
4. Failed jobs use the existing retry/backoff policy. The workflow has a 10-minute timeout.

The workflow uses read-only repository permissions and does not deploy or modify the Render web service.

## Important limitations

- This is periodic processing, **not a continuously running worker**. Newly queued jobs can wait until the next run, and GitHub may delay scheduled events.
- GitHub Actions usage limits and billing depend on repository visibility and account plan. Check the current Actions quota before relying on it for production.
- CSV ingestion is handled by the existing worker. PDFs are intentionally moved to `NEEDS_PDF_PROCESSING` because OCR/extraction is not implemented yet.
- The workflow does not make PDF extraction, OCR, malware scanning, or external registry validation available by itself.
- Review the Actions logs and database job statuses after the first manual run. Logs should not contain secret values.

## First-run checklist

1. Merge the workflow and worker changes into `main` after review.
2. Configure all six GitHub Actions secrets listed above.
3. Open **Actions → Scheduled ingestion batch → Run workflow**.
4. Confirm the run succeeds and the job status changes as expected in Supabase.
5. Check that a CSV test import produces the expected inserted/updated/skipped counts. For a PDF test, expect `NEEDS_PDF_PROCESSING`, not successful extraction.
