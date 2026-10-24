-- Apply after 001-010. Defence in depth for Supabase/PostgREST: the API and worker connect with a
-- trusted server-side role; browser-facing roles (anon, authenticated) must never reach these tables.
-- Row level security is enabled with no policies (deny by default) AND privileges are revoked.
DO $$
DECLARE
  t text;
  tables text[] := ARRAY['internal_organizations','organization_record_versions','registry_sources','ingestion_jobs',
    'ingestion_row_errors','ingestion_audit_logs','warehouse_raw_imports','warehouse_access_logs',
    'failed_imports_dlq','api_keys','api_key_audit_events'];
  r text;
BEGIN
  FOREACH t IN ARRAY tables LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
      FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
          EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %I', t, r);
        END IF;
      END LOOP;
    END IF;
  END LOOP;
  IF to_regclass('public.warehouse_organizations') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.warehouse_organizations SET (security_invoker = true)';
    FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE public.warehouse_organizations FROM %I', r);
      END IF;
    END LOOP;
  END IF;
  -- Tables created by future migrations must not be readable by browser roles by default.
  FOREACH r IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', r);
    END IF;
  END LOOP;
END $$;
