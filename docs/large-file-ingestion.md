# Large-file ingestion

## Upload paths
- The ordinary API upload endpoint is intentionally capped by MAX_UPLOAD_BYTES (50 MiB by default) and is appropriate for small files and local development.
- Files larger than 50 MiB use the authenticated presign/complete flow: POST /api/v1/ingestion/uploads/presign with file_name and size_bytes, PUT the bytes to the returned upload_url using the exact returned Content-Type, then POST /api/v1/ingestion/uploads/{job_id}/complete.
- MAX_DIRECT_UPLOAD_BYTES defaults to 5 GiB for a single presigned PUT. Larger objects need a multipart-upload protocol; do not raise this limit beyond the storage provider's supported single-PUT size.
- Presigned URLs are bearer capabilities. Keep them out of logs, analytics, support tickets and persistent browser storage. They expire after DIRECT_UPLOAD_URL_TTL_SECONDS.

## Cloudflare R2 prerequisites
Use the existing private R2 bucket. Configure its CORS policy to allow only the required dashboard origins, the PUT method, and the Content-Type request header. Do not make the bucket public. The deployment must set the existing R2 credentials server-side; no credentials are returned to the browser.

## Integrity and PDF handling
The completion endpoint verifies that the object exists, matches the declared byte size, and has a compatible file signature before changing the job from UPLOADING to QUEUED. This is not malware scanning or business-document verification. CSV processing is bounded by row batches and persisted row progress. PDF diagnostics are capped at 50 MiB; larger PDFs remain in private storage with NEEDS_PDF_PROCESSING and require manual review without being loaded into application memory.

## Runtime capacity caveat
The current GitHub Actions worker is a bounded scheduled batch runner, not a continuously running large-file worker. Row progress is committed in batches so jobs can resume after interruption, but a scheduled runner still needs to download the object on a new run and has a finite job timeout. Before declaring multi-gigabyte throughput production-ready, benchmark representative files and either confirm completion within the existing runner limits or approve a longer-lived worker with adequate persistent scratch storage. Do not provision paid infrastructure without explicit approval.

## Local development
R2 direct uploads are unavailable when R2 is blank in the Windows local compose stack. Use the ordinary upload endpoint for sample files under MAX_UPLOAD_BYTES. Large-file presign tests should mock R2 rather than use production storage.