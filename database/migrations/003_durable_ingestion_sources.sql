-- Apply after migrations 001 and 002. Safe to rerun on PostgreSQL.
CREATE TABLE IF NOT EXISTS registry_sources (
 id varchar(36) PRIMARY KEY,
 source_key varchar(100) NOT NULL UNIQUE,
 display_name varchar(200) NOT NULL,
 jurisdiction varchar(100) NOT NULL DEFAULT 'KE',
 source_type varchar(40) NOT NULL DEFAULT 'IMPORTED_DATASET',
 authority_url varchar(1000),
 licence_reference varchar(500),
 freshness_sla_hours integer,
 precedence integer NOT NULL DEFAULT 100,
 enabled boolean NOT NULL DEFAULT true,
 notes text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS content_type varchar(200);
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS source_id varchar(36) REFERENCES registry_sources(id);
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS source_name varchar(200);
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS idempotency_key varchar(200);
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS attempts integer NOT NULL DEFAULT 0;
ALTER TABLE ingestion_jobs ADD COLUMN IF NOT EXISTS started_at timestamptz;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ingestion_jobs_idempotency ON ingestion_jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_ingestion_jobs_status_created ON ingestion_jobs(status,created_at);
CREATE TABLE IF NOT EXISTS ingestion_row_errors (
 id varchar(36) PRIMARY KEY,
 job_id varchar(36) NOT NULL REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
 row_number integer,
 error_code varchar(80) NOT NULL,
 message text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ingestion_row_errors_job_row ON ingestion_row_errors(job_id,row_number);
