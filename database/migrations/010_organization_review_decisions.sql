-- Additive migration. Apply only after reviewing the target database and backup/rollback plan.
CREATE TABLE IF NOT EXISTS organization_review_decisions (
  id varchar(36) PRIMARY KEY,
  organization_id varchar(36) NOT NULL REFERENCES internal_organizations(id) ON DELETE RESTRICT,
  decision varchar(40) NOT NULL CHECK (decision IN ('possible_duplicate','not_duplicate','needs_more_evidence','record_incorrect','reopened')),
  reason text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  reviewer varchar(200) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_org_review_decisions_org_created
  ON organization_review_decisions(organization_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS ix_org_review_decisions_decision_created
  ON organization_review_decisions(decision, created_at DESC);

-- The service database role should own/use this table. It is not intended for direct browser access.
ALTER TABLE public.organization_review_decisions ENABLE ROW LEVEL SECURITY;
DO $
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.organization_review_decisions FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.organization_review_decisions FROM authenticated';
  END IF;
END $;
