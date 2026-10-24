-- Apply after 001-009. Mirrors Alembic revisions 0005 and 0007.
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS heartbeat_at timestamptz;
CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_status_next_attempt ON ingestion_jobs(status, next_attempt_at);
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS ix_org_normalized_name_trgm ON internal_organizations USING gin (normalized_legal_name gin_trgm_ops);
