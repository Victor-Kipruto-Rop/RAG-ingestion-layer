-- Durable, auditable human decisions for fuzzy entity-match candidates.
-- Decisions are review metadata only and never merge or mutate organization records.
CREATE TABLE IF NOT EXISTS public.entity_match_reviews (
  id varchar(36) PRIMARY KEY,
  candidate_organization_id varchar(36) NOT NULL
    REFERENCES public.internal_organizations(id) ON DELETE RESTRICT,
  query_name varchar(500) NOT NULL,
  decision varchar(30) NOT NULL CHECK (decision IN ('accepted_candidate','rejected_candidate','needs_more_evidence')),
  comment text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  reviewer_id varchar(120) NOT NULL,
  request_id varchar(100),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_entity_match_reviews_candidate_created
  ON public.entity_match_reviews(candidate_organization_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_entity_match_reviews_decision_created
  ON public.entity_match_reviews(decision, created_at DESC);
ALTER TABLE public.entity_match_reviews ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.entity_match_reviews FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.entity_match_reviews FROM authenticated';
  END IF;
END $$;
