-- Additive migration. Review target schema and backup before applying to production.
-- Raw API key secrets are never stored; only SHA-256 digests and public prefixes are persisted.
CREATE TABLE IF NOT EXISTS api_keys (
 id varchar(36) PRIMARY KEY, name varchar(120) NOT NULL, key_prefix varchar(40) NOT NULL UNIQUE,
 secret_hash varchar(64) NOT NULL UNIQUE, environment varchar(16) NOT NULL CHECK (environment IN ('sandbox','production')),
 scopes jsonb NOT NULL DEFAULT '["registry:read"]'::jsonb,
 status varchar(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
 expires_at timestamptz, created_by varchar(200) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 last_used_at timestamptz, revoked_at timestamptz, rotated_from_id varchar(36) REFERENCES api_keys(id),
 CONSTRAINT ck_api_keys_revocation CHECK ((status='active' AND revoked_at IS NULL) OR (status='revoked' AND revoked_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS ix_api_keys_environment_status ON api_keys(environment,status);
CREATE INDEX IF NOT EXISTS ix_api_keys_created_at ON api_keys(created_at DESC);
CREATE TABLE IF NOT EXISTS api_key_security_events (
 id varchar(36) PRIMARY KEY, api_key_id varchar(36) REFERENCES api_keys(id) ON DELETE SET NULL,
 key_prefix varchar(40), event_type varchar(60) NOT NULL, expected_environment varchar(16), key_environment varchar(16),
 endpoint varchar(300) NOT NULL, request_id varchar(100), source_ip varchar(64),
 details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_key_security_events_created_at ON api_key_security_events(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_api_key_security_events_key_id ON api_key_security_events(api_key_id);
