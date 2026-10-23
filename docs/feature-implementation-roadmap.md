# Datasource feature implementation roadmap

This is the implementation sequence for the Datasource product roadmap. Features are not considered complete until code, tests, migrations, documentation, and required deployment configuration have been reviewed. Production migrations and deployments require separate approval.

## Phase 1 — API key security and access control
**Status: implementation submitted for review in PR #18; CI/review and migration rollout still pending.**

- [x] Managed sandbox and production key formats.
- [x] Hash-only persistence and one-time secret display.
- [x] Environment mismatch rejection with a security event.
- [x] Scope checks, expiry, last-used tracking, rotation and revocation.
- [x] Operator-only management endpoints and configuration documentation.
- [x] SQL and Alembic schema migrations plus focused regression tests.
- [ ] Confirm CI passes and review all changes.
- [ ] Configure a strong server-side `KEY_MANAGEMENT_TOKEN` and deployment-specific `DATASOURCE_ENVIRONMENT`.
- [ ] Apply one approved migration path to the intended database.
- [ ] Migrate existing callers away from legacy shared keys.
- [ ] Build customer-facing key management only after authenticated user/organization ownership exists.

## Phase 2 — Ingestion reliability
- Stream large CSVs instead of loading whole files into memory.
- Add XLSX parsing with strict size, row, sheet, formula, and type limits.
- Add upload preview, column mapping, validation summaries, and import confirmation.
- Persist row-level progress, retry state, idempotency, and resumable processing.
- Provide downloadable sanitized error reports and safe retry/reprocess actions.
- Add duplicate-upload detection, checksums, cancellation, and import rollback/compensation strategy.
- Add worker queue depth, processing leases, stuck-job recovery, and upload malware scanning/quarantine policy.

## Phase 3 — Data quality and registry intelligence
- Add field-level validation rules and configurable required-field policies.
- Calculate explainable record-quality scores from actual checks.
- Detect duplicate candidates, identifier conflicts, stale records, and cross-source discrepancies.
- Preserve source attribution, evidence, confidence, lineage, and record-version history.
- Add human review queues; never auto-merge records solely from name similarity.
- Add searchable quality reports and auditable bulk correction workflows.

## Phase 4 — External verification integrations
- Create a provider-adapter contract for BRS, KRA PIN, and approved commercial providers.
- Store credentials only in server-side secret management and verify provider permissions before use.
- Normalize provider responses without discarding raw evidence or provider reference IDs.
- Add timeout, retry/backoff, circuit-breaker, idempotency, cost/usage tracking, and provider health checks.
- Represent results truthfully as verified, not found, inconclusive, pending, provider unavailable, or manual review.
- Add consent/purpose tracking, retention controls, and audit trails before handling sensitive verification data.
- Do not claim an integration is live until credentials, permissions, contract, and end-to-end tests are verified.

## Phase 5 — Developer experience
- Publish environment-specific API reference and examples.
- Add a protected API explorer, request/response samples, and error-code catalogue.
- Add webhook registration, signed delivery, retries, replay protection, and delivery history.
- Add idempotency guidance, API version policy, deprecation notices, changelog, and request correlation IDs.
- Add per-key usage analytics, quota headers, rate-limit responses, and safe key rotation guidance.
- Add customer self-service key management only after identity, organization membership, and role checks are implemented.

## Phase 6 — Production operations and security
- Add operator dashboards for service health, queue age, error rates, latency percentiles, storage, and provider health.
- Add alert thresholds, incident runbooks, backup/restore drills, and tested rollback procedures.
- Enforce least-privilege roles, secret rotation, access reviews, retention/deletion policies, and audit-log access controls.
- Add dependency/container scanning, secret scanning, security regression tests, and load tests.
- Add production readiness checks and an explicit release checklist; never use synthetic data to claim live health.
- Keep sandbox and production databases, credentials, storage, queues, and deployment configuration separated.

## Phase 7 — Commercial and customer operations
- Add plan/usage definitions only after metering and billing requirements are agreed.
- Track billable events with idempotent, auditable usage records.
- Add customer integration inventory, quotas, usage exports, and service notifications.
- Add organization monitoring and scheduled re-checks only with a lawful purpose, customer consent/authority, and provider support.
- Add invoicing/subscription integration after pricing, tax, refund, and support processes are defined.

## Release gates

Each phase must include focused automated tests, a full CI run, migration review, updated docs, and a rollback plan. Do not apply migrations to production, change production secrets, merge, or deploy as part of a code-generation step without explicit approval.
