-- Apply to the configured PostgreSQL database before setting APP_ENV=production.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS internal_organizations (
 id varchar(36) PRIMARY KEY, legal_name varchar(500) NOT NULL, normalized_legal_name varchar(500) NOT NULL,
 registration_number varchar(120), normalized_registration_number varchar(120), tax_pin varchar(80), normalized_tax_pin varchar(80),
 status varchar(30) NOT NULL DEFAULT 'ACTIVE', registry_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 source_file varchar(500), source_row integer, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT uq_org_registration UNIQUE(normalized_registration_number)
);
CREATE INDEX IF NOT EXISTS ix_internal_organizations_normalized_legal_name ON internal_organizations(normalized_legal_name);
CREATE INDEX IF NOT EXISTS ix_internal_organizations_name_trgm ON internal_organizations USING gin(normalized_legal_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_internal_organizations_registration ON internal_organizations(normalized_registration_number);
CREATE INDEX IF NOT EXISTS ix_internal_organizations_tax_pin ON internal_organizations(normalized_tax_pin);
CREATE TABLE IF NOT EXISTS ingestion_jobs (
 id varchar(36) PRIMARY KEY, file_name varchar(500) NOT NULL, object_key varchar(1000), status varchar(40) NOT NULL DEFAULT 'QUEUED',
 records_processed integer NOT NULL DEFAULT 0, records_inserted integer NOT NULL DEFAULT 0, records_updated integer NOT NULL DEFAULT 0,
 records_skipped integer NOT NULL DEFAULT 0, error_summary text, created_at timestamptz NOT NULL DEFAULT now(), completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS ingestion_audit_logs (
 id varchar(36) PRIMARY KEY, action varchar(100) NOT NULL, actor varchar(200) NOT NULL,
 file_name varchar(500), details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
