# Entity match review workflow

This feature records an auditable human decision on a fuzzy match candidate. It does not merge organizations, certify legal identity, or mutate the canonical registry record.

## Enablement

1. Review and apply `database/migrations/010_entity_match_reviews.sql` to the target PostgreSQL database after backup and explicit approval.
2. Create a managed API key with `registry:read` and `quality:review` scopes for the trusted review service.
3. Keep the key server-side. The current operator-token key manager is not customer tenant authentication.

## API

- `GET /api/v1/quality/reviews?limit=50&offset=0` lists review decisions.
- `POST /api/v1/quality/reviews` stores a decision:
  ```json
  {
    "candidate_organization_id": "existing-organization-id",
    "query_name": "Example Limited",
    "decision": "needs_more_evidence",
    "comment": "Registration identifier conflicts with the source record.",
    "evidence": {"source": "approved-import", "reason_code": "identifier_conflict"}
  }
  ```
- Valid decisions: `accepted_candidate`, `rejected_candidate`, `needs_more_evidence`.
- POST requires the `quality:review` scope. GET requires `registry:read`.
- Evidence is limited to 12 KB; do not include personal data or raw documents in review metadata.
- Every decision writes an audit event. The result explicitly states `review_only_no_record_merge`.

## Provider adapter boundary

`backend/src/provider_adapters.py` contains explicit not-configured adapters for BRS and KRA. They do not make network calls or claim to verify data. Replace them only after credentials, API contracts, allowed purpose, rate limits, and data-processing terms are approved and tested.
