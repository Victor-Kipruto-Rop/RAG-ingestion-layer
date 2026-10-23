-- Additive migration. Review and apply separately per environment after backup/schema comparison.
CREATE TABLE IF NOT EXISTS public.quality_review_cases (
  id varchar(36) PRIMARY KEY,
  organization_id varchar(36) NOT NULL REFERENCES public.internal_organizations(id) ON DELETE RESTRICT,
  related_organization_id varchar(36) NULL REFERENCES public.internal_organizations(id) ON DELETE RESTRICT,
  case_type varchar(40) NOT NULL CHECK (case_type IN ('possible_duplicate','identifier_conflict','missing_data','stale_record','source_conflict','other')),
  status varchar(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_review','resolved','dismissed')),
  severity varchar(20) NOT NULL DEFAULT 'review' CHECK (severity IN ('low','review','high')),
  summary varchar(1000) NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by varchar(200) NOT NULL,
  assigned_to varchar(200) NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_quality_review_cases_status_created ON public.quality_review_cases(status, created_at);
CREATE INDEX IF NOT EXISTS ix_quality_review_cases_org_created ON public.quality_review_cases(organization_id, created_at);
CREATE INDEX IF NOT EXISTS ix_quality_review_cases_type_status ON public.quality_review_cases(case_type, status);

CREATE TABLE IF NOT EXISTS public.quality_review_decisions (
  id varchar(36) PRIMARY KEY,
  case_id varchar(36) NOT NULL REFERENCES public.quality_review_cases(id) ON DELETE RESTRICT,
  decision varchar(40) NOT NULL CHECK (decision IN ('same_entity','different_entities','needs_more_evidence','data_quality_issue','dismissed')),
  notes text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  reviewer_ref varchar(200) NOT NULL,
  request_id varchar(100) NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_quality_review_decisions_case_created ON public.quality_review_decisions(case_id, created_at);
CREATE INDEX IF NOT EXISTS ix_quality_review_decisions_case_id ON public.quality_review_decisions(case_id);

ALTER TABLE public.quality_review_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quality_review_decisions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.quality_review_cases FROM anon';
    EXECUTE 'REVOKE ALL ON TABLE public.quality_review_decisions FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.quality_review_cases FROM authenticated';
    EXECUTE 'REVOKE ALL ON TABLE public.quality_review_decisions FROM authenticated';
  END IF;
END $$;
