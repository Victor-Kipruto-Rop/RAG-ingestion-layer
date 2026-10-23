# Production Platform Implementation Roadmap

This roadmap tracks code delivered on feature branches. Production rollout remains gated on review, migrations, configuration and CI.

## Phase 1 — Environment-scoped API keys
- [x] Add random sandbox/production credentials; store SHA-256 digests only.
- [x] Enforce environment match from server configuration, not request headers.
- [x] Add key scopes, expiration, rotation, revocation and security events.
- [x] Add operator-only management endpoints and audit events.
- [ ] Configure a strong DATASOURCE_ADMIN_TOKEN and apply migration separately in each environment.
- [ ] Add browser/API integration tests against a disposable database.

## Phase 2 — Ingestion reliability and data quality
- [x] Add quality summary metrics and review-only fuzzy match candidates.
- [x] Expose source freshness as unknown until successful import timestamps are persisted.
- [x] Keep job status/progress sourced from persisted backend records.
- [ ] Add end-to-end worker regression tests and digest-based duplicate upload handling.

## Phase 3 — Provider integration foundations
- [x] Add a typed provider-adapter contract with explicit pending/unavailable/manual-review states.
- [ ] Configure BRS/KRA provider credentials and perform vendor-approved integration tests.
- [ ] Persist provider evidence, consent and review outcomes before claiming verification.

## Phase 4 — Developer experience and operations
- [x] Document environment separation, API-key management, quality endpoints and provider boundaries.
- [x] Keep structured request/job correlation and Prometheus endpoint already present in the service.
- [ ] Add alerts, provider latency metrics and operational dashboards after deployment configuration is agreed.

## Phase 5 — Dashboard and release verification
- [x] Add an operator API-key management screen that never persists the admin token in local storage.
- [ ] Run frontend build, pytest, and CI; fix all actionable failures before merge.
- [ ] Apply migration only after schema review; deploy only with explicit approval.

## Security boundaries
- A single DATASOURCE_ADMIN_TOKEN is an operator control, not end-user identity or multi-tenant RBAC. Do not expose it to public users. Tenant/user self-service key management requires an authenticated identity provider and organization membership model.
- Legacy REGISTRY_API_KEYS remain for migration compatibility; migrate callers to managed keys and retire shared keys deliberately.
- A fuzzy match is a review candidate, never proof of identity. External provider integrations are not activated by adding the adapter interface.
