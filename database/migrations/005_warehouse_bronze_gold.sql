-- Phase 1: warehouse layers. Apply after migrations 001-004.
-- Bronze: immutable upload metadata. The raw bytes remain in private Cloudflare R2.
CREATE TABLE IF NOT EXISTS warehouse_raw_imports (
 id varchar(36) PRIMARY KEY,
 ingestion_job_id varchar(36) NOT NULL UNIQUE REFERENCES ingestion_jobs(id) ON DELETE CASCADE,
 object_key varchar(1000) NOT NULL,
 original_filename varchar(500) NOT NULL,
 content_type varchar(200),
 byte_size bigint NOT NULL DEFAULT 0,
 sha256_hex char(64),
 source_id varchar(36) REFERENCES registry_sources(id),
 source_name varchar(200),
 source_published_at timestamptz,
 uploaded_by varchar(200) NOT NULL DEFAULT 'internal-service',
 import_status varchar(40) NOT NULL DEFAULT 'QUEUED',
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_warehouse_raw_imports_created ON warehouse_raw_imports(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_warehouse_raw_imports_status ON warehouse_raw_imports(import_status);
CREATE INDEX IF NOT EXISTS ix_warehouse_raw_imports_sha256 ON warehouse_raw_imports(sha256_hex);
-- Gold: latency, outcome and caller metadata; never store API keys or raw request secrets.
CREATE TABLE IF NOT EXISTS warehouse_access_logs (
 id varchar(36) PRIMARY KEY,
 request_id varchar(100),
 caller_service varchar(200) NOT NULL DEFAULT 'unknown',
 endpoint varchar(300) NOT NULL,
 http_method varchar(12) NOT NULL,
 response_status integer NOT NULL,
 duration_ms numeric(12,3) NOT NULL DEFAULT 0,
 outcome varchar(40) NOT NULL DEFAULT 'UNKNOWN',
 query_type varchar(40),
 result_count integer,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_warehouse_access_logs_created ON warehouse_access_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_warehouse_access_logs_endpoint_created ON warehouse_access_logs(endpoint,created_at DESC);
CREATE INDEX IF NOT EXISTS ix_warehouse_access_logs_caller_created ON warehouse_access_logs(caller_service,created_at DESC);
-- Compatibility view: canonical silver records live in internal_organizations.
CREATE OR REPLACE VIEW warehouse_organizations AS
 SELECT id,legal_name,normalized_legal_name,registration_number,normalized_registration_number,
 tax_pin,normalized_tax_pin,status,registry_payload,source_file,source_row,source_name,
 source_record_id,source_published_at,last_seen_at,data_quality_status,created_at,updated_at
 FROM internal_organizations;
