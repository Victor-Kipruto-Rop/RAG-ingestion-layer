-- Persist the last committed CSV row so retried jobs can resume after bounded batches.
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS last_processed_row integer NOT NULL DEFAULT 1;
