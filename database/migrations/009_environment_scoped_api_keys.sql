-- Apply after migrations 001-008. API secrets are never stored in plaintext.
CREATE TABLE IF NOT EXISTS api_keys (
  id varchar(36) PRIMARY KEY,
  organization_id varchar(200) NOT NULL,
  created_by_user_id varchar(200) NOT NULL,
  name varchar(100) NOT NULL,
  environment varchar(20) NOT NULL CHECK (environment IN ('sandbox','production')),
  key_prefix varchar(32) NOT NULL,
  secret_hash varchar(64) NOT NULL UNIQUE,
  scopes jsonb NOT NULL DEFAULT '["registry:read"]'::jsonb,
  status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz,
  expires_at timestamptz,
  revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_api_keys_org_created ON api_keys(organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_api_keys_status_environment ON api_keys(status, environment);
CREATE TABLE IF NOT EXISTS api_key_audit_events (
  id varchar(36) PRIMARY KEY,
  organization_id varchar(200) NOT NULL,
  actor_user_id varchar(200) NOT NULL,
  api_key_id varchar(36),
  action varchar(80) NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_key_audit_org_created ON api_key_audit_events(organization_id, created_at DESC);

-- Client SDKs must never access key hashes or audit evidence directly.
-- The trusted backend database role remains responsible for server-side access.
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_key_audit_events ENABLE ROW LEVEL SECURITY;
