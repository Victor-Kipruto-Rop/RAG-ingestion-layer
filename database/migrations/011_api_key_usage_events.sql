-- API usage telemetry stores identifiers and outcomes only; never store request headers or raw API secrets.
CREATE TABLE IF NOT EXISTS api_key_usage_events (
 id varchar(36) PRIMARY KEY,
 api_key_id varchar(36) REFERENCES api_keys(id) ON DELETE SET NULL,
 key_prefix varchar(40),
 environment varchar(16),
 endpoint varchar(300) NOT NULL,
 http_method varchar(12) NOT NULL,
 response_status integer NOT NULL,
 duration_ms double precision NOT NULL DEFAULT 0,
 request_id varchar(100),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_key_usage_events_key_created ON api_key_usage_events(api_key_id,created_at DESC);
CREATE INDEX IF NOT EXISTS ix_api_key_usage_events_created ON api_key_usage_events(created_at DESC);
