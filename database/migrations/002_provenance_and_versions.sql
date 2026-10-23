-- Apply after 001_initial.sql. Safe to rerun on PostgreSQL.
ALTER TABLE internal_organizations ADD COLUMN IF NOT EXISTS source_name varchar(200);
ALTER TABLE internal_organizations ADD COLUMN IF NOT EXISTS source_record_id varchar(200);
ALTER TABLE internal_organizations ADD COLUMN IF NOT EXISTS source_published_at timestamptz;
ALTER TABLE internal_organizations ADD COLUMN IF NOT EXISTS last_seen_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE internal_organizations ADD COLUMN IF NOT EXISTS data_quality_status varchar(30) NOT NULL DEFAULT 'UNREVIEWED';
CREATE INDEX IF NOT EXISTS ix_org_source_name ON internal_organizations(source_name);
CREATE INDEX IF NOT EXISTS ix_org_last_seen_at ON internal_organizations(last_seen_at);
CREATE INDEX IF NOT EXISTS ix_org_data_quality_status ON internal_organizations(data_quality_status);
CREATE TABLE IF NOT EXISTS organization_record_versions (
 id varchar(36) PRIMARY KEY,
 organization_id varchar(36) NOT NULL REFERENCES internal_organizations(id) ON DELETE CASCADE,
 change_type varchar(30) NOT NULL,
 snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
 source_name varchar(200),
 source_file varchar(500),
 source_row integer,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_org_record_versions_org_created ON organization_record_versions(organization_id, created_at DESC);
