-- Additive verification orchestration schema. No provider is assumed live by this migration.
CREATE TABLE IF NOT EXISTS verification_cases (
 id varchar(36) PRIMARY KEY,
 subject_type varchar(40) NOT NULL DEFAULT 'organization',
 legal_name varchar(500),
 registration_number varchar(120),
 tax_pin varchar(80),
 status varchar(40) NOT NULL DEFAULT 'not_configured',
 correlation_id varchar(100),
 requested_by varchar(200) NOT NULL DEFAULT 'internal-service',
 result_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_verification_cases_status_created ON verification_cases(status,created_at DESC);
CREATE INDEX IF NOT EXISTS ix_verification_cases_registration ON verification_cases(registration_number);
CREATE INDEX IF NOT EXISTS ix_verification_cases_correlation ON verification_cases(correlation_id);

CREATE TABLE IF NOT EXISTS verification_provider_checks (
 id varchar(36) PRIMARY KEY,
 case_id varchar(36) NOT NULL REFERENCES verification_cases(id) ON DELETE CASCADE,
 provider_key varchar(80) NOT NULL,
 status varchar(40) NOT NULL DEFAULT 'not_configured',
 provider_reference varchar(200),
 response_code varchar(100),
 safe_result jsonb NOT NULL DEFAULT '{}'::jsonb,
 error_category varchar(100),
 started_at timestamptz,
 completed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_verification_provider_checks_case ON verification_provider_checks(case_id,created_at DESC);
