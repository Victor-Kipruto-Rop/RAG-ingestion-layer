-- Persist request correlation IDs through asynchronous ingestion.
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS correlation_id varchar(100);
CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_correlation_id ON ingestion_jobs(correlation_id);
