-- Managed environment-scoped API keys; additive migration, review and apply separately per environment.
CREATE TABLE IF NOT EXISTS managed_api_keys (
  id varchar(36) PRIMARY KEY,
  name varchar(120) NOT NULL,
  environment varchar(20) NOT NULL CHECK (environment IN ('sandbox','production')),
  key_prefix varchar(80) NOT NULL UNIQUE,
  secret_hash varchar(64) NOT NULL UNIQUE,
  scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
  status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  created_by varchar(120) NOT NULL DEFAULT 'operator',
  created_at timestamptz NOT NULL DEFAULT now(),
  last_used_at timestamptz NULL,
  expires_at timestamptz NULL,
  revoked_at timestamptz NULL,
  rotated_from_id varchar(36) NULL REFERENCES managed_api_keys(id)
);
CREATE INDEX IF NOT EXISTS ix_managed_api_keys_environment_status ON managed_api_keys(environment,status);
CREATE TABLE IF NOT EXISTS api_key_security_events (
  id varchar(36) PRIMARY KEY,
  key_id varchar(36) NULL,
  key_prefix varchar(80) NULL,
  event_type varchar(80) NOT NULL,
  expected_environment varchar(20) NULL,
  key_environment varchar(20) NULL,
  endpoint varchar(300) NULL,
  http_method varchar(12) NULL,
  request_id varchar(100) NULL,
  client_ip varchar(80) NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_key_security_events_created_at ON api_key_security_events(created_at);
CREATE INDEX IF NOT EXISTS ix_api_key_security_events_key_id ON api_key_security_events(key_id);

-- These tables contain credential digests and security metadata; expose only to the trusted backend role.
ALTER TABLE public.managed_api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_key_security_events ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.managed_api_keys FROM anon, authenticated;
REVOKE ALL ON TABLE public.api_key_security_events FROM anon, authenticated;
