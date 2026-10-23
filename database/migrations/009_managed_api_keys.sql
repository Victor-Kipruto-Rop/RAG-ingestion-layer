-- Phase 1: managed environment-isolated API keys.
-- Apply only after reviewing the target database and approved migration window.
CREATE TABLE IF NOT EXISTS managed_api_keys (
    id varchar(36) PRIMARY KEY,
    name varchar(120) NOT NULL,
    environment varchar(20) NOT NULL CHECK (environment IN ('sandbox', 'production')),
    key_prefix varchar(32) NOT NULL UNIQUE,
    key_hash varchar(64) NOT NULL,
    scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked', 'expired')),
    created_by varchar(100) NOT NULL DEFAULT 'service-operator',
    rotated_from_id varchar(36),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz,
    expires_at timestamptz,
    revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS ix_managed_api_keys_environment ON managed_api_keys(environment);
CREATE INDEX IF NOT EXISTS ix_managed_api_keys_status ON managed_api_keys(status);
CREATE INDEX IF NOT EXISTS ix_managed_api_keys_environment_status ON managed_api_keys(environment, status);
CREATE TABLE IF NOT EXISTS api_key_security_events (
    id varchar(36) PRIMARY KEY,
    key_id varchar(36),
    key_prefix varchar(32),
    event_type varchar(60) NOT NULL,
    requested_environment varchar(20) NOT NULL,
    endpoint varchar(300) NOT NULL,
    request_id varchar(100),
    details varchar(500),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_key_security_events_key_id ON api_key_security_events(key_id);
CREATE INDEX IF NOT EXISTS ix_api_key_security_events_event_type ON api_key_security_events(event_type);
CREATE INDEX IF NOT EXISTS ix_api_key_events_created_at ON api_key_security_events(created_at);
