-- Durable DLQ for invalid imported rows. Detailed diagnostics must remain access-controlled.
CREATE TABLE IF NOT EXISTS public.failed_imports_dlq (
  id varchar(36) PRIMARY KEY,
  job_id varchar(36) NOT NULL REFERENCES public.ingestion_jobs(id) ON DELETE RESTRICT,
  row_number integer NOT NULL,
  error_code varchar(80) NOT NULL,
  error_type varchar(200) NOT NULL,
  message text NOT NULL,
  sanitized_row jsonb NOT NULL DEFAULT '{}'::jsonb,
  traceback_text text NOT NULL,
  resolved_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_failed_import_job_row_code UNIQUE(job_id, row_number, error_code)
);
CREATE INDEX IF NOT EXISTS ix_failed_imports_dlq_job_id ON public.failed_imports_dlq(job_id);
CREATE INDEX IF NOT EXISTS ix_failed_imports_dlq_created_at ON public.failed_imports_dlq(created_at);
