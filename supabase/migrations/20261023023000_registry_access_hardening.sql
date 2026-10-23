-- Restrict the internal registry warehouse to trusted server-side roles.
-- Safe to re-run. The worker/API connects directly using a trusted database role.
ALTER VIEW public.warehouse_organizations SET (security_invoker = true);

REVOKE ALL PRIVILEGES ON TABLE
  public.warehouse_organizations,
  public.internal_organizations,
  public.ingestion_jobs,
  public.ingestion_audit_logs,
  public.ingestion_row_errors,
  public.organization_record_versions,
  public.registry_sources,
  public.warehouse_raw_imports,
  public.warehouse_access_logs
FROM PUBLIC, anon, authenticated;

-- Do not grant anon/authenticated access back here. Access is server-side only.
-- service_role retains its existing access; this migration does not expose
-- the Supabase service_role key to clients.
