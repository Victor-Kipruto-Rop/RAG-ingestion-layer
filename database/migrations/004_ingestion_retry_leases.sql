-- Apply after migrations 001, 002 and 003.
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;
CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_next_attempt_at ON ingestion_jobs(next_attempt_at);
