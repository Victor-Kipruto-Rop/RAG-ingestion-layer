# Phase 2 — Ingestion reliability

## Implemented in this phase

- Durable upload intake: bounded upload size, extension/signature checks, SHA-256 on ordinary uploads, idempotency keys, duplicate detection, private object storage, and a presigned direct-upload completion handshake.
- Resumable CSV imports: disk-backed file spooling, bounded row batches, committed row checkpoints, retry limits/backoff, stale-worker recovery, and SKIP LOCKED job claiming on PostgreSQL.
- Safe record processing: normalized fields, exact identifier upserts, source provenance, record versions, possible-duplicate candidates for manual review, and per-row validation errors.
- Failure isolation: sanitized row diagnostics, a restricted dead-letter table, and row-error pagination.
- PDF handling: signature and size checks, bounded text/OCR diagnostics, explicit OCR configuration, and manual-review status. Extracted text is never treated as verified data.
- Operational recovery: per-job inspection, explicit retry for failed CSV jobs from their last committed checkpoint, paginated dead-letter diagnostics, and streamed CSV error reports.
- Observability: correlation IDs, job audit events, queue/throughput metrics, and health endpoints.

## Operational API

All endpoints require the existing server-side API-key authentication.

- GET /api/v1/ingestion/jobs/{job_id} — job status, counters, committed checkpoint, file checksum and next retry time.
- POST /api/v1/ingestion/jobs/{job_id}/retry — retry a failed CSV from the last committed checkpoint. It deliberately does not replay already committed rows. PDF jobs remain manual-review-only.
- GET /api/v1/ingestion/jobs/{job_id}/errors.csv — stream a spreadsheet-safe CSV of row errors.
- GET /api/v1/ingestion/jobs/{job_id}/dead-letter?page=1&page_size=100 — sanitized, paginated failed-row diagnostics without raw tracebacks.
- GET /api/v1/ingestion/jobs/{job_id}/errors?page=1&page_size=100 — existing paginated row-error API.
- POST /api/v1/ingestion/uploads/presign, PUT to the returned URL, then POST /api/v1/ingestion/uploads/{job_id}/complete — direct R2 upload flow for larger files.

## Status and retry rules

- UPLOADING: a direct upload has been allocated but not completed.
- QUEUED: eligible for worker pickup, subject to next_attempt_at.
- PROCESSING: a worker has claimed the job.
- COMPLETED / COMPLETED_WITH_ERRORS: CSV processing finished, with the latter indicating row-level skips.
- FAILED: attempts exhausted or a non-recoverable processing error occurred.
- NEEDS_PDF_PROCESSING: PDF diagnostics finished but data extraction is not accepted as authoritative and manual review is required.

The last_processed_row checkpoint is the last committed CSV row number (the CSV header is row 1). A manual retry preserves counters and the checkpoint. Do not reset a job to row 1 unless an operator has reviewed whether replaying prior rows would create unwanted record-version history.

## Safety and release boundaries

- This phase adds API routes and documentation; it does not apply SQL migrations, run production ingestion jobs, change production secrets, or deploy.
- Apply the existing migrations in order before using these routes against a database missing the ingestion/DLQ tables.
- Validate with the backend test suite and CI. Test outcomes must be recorded from actual runs; source changes alone are not evidence that CI passed.
- Large CSVs are streamed through disk-backed spooling, but still need representative load tests on the target worker's CPU, disk and timeout limits.
- Direct R2 uploads use a declared size and object metadata check; this is not malware scanning. Use a quarantine/scanning service before processing untrusted uploads in production if the threat model requires it.
