# Provider Adapter Contract

## Purpose
The src.providers package provides a normalized adapter contract and an explicit unavailable implementation. It is not a live BRS, KRA, or IPRS integration.

## Required behavior
1. Declare a stable provider name.
2. Implement registration or tax-PIN checks only where authorized by the provider contract.
3. Return verified, not_found, manual_review, unavailable, or error.
4. Include UTC check time, provider reference where available, matched fields, and evidence provenance.
5. Return unavailable when credentials, configuration, network access, or required contract fields are missing.
6. Never fabricate a successful result or infer a positive match from HTTP 200 alone.
7. Use bounded timeouts and a retry budget; do not retry validation failures indefinitely.
8. Avoid logging credentials, full tax identifiers, document contents, or raw provider payloads.
9. Retain raw responses only when approved by provider terms and data-retention policy.
10. Preserve correlation IDs and sanitized metadata for incident review.

## State mapping
- verified: positive provider result under its configured contract; application policy must still run.
- not_found: provider confirms no matching record; this is not evidence of fraud.
- manual_review: incomplete data, conflicting identifiers, document mismatch, or inconclusive response.
- unavailable: credentials missing, provider timeout budget exhausted, or provider maintenance.
- error: malformed response or non-retryable provider error.

## Go-live checklist
- Review contract and documentation.
- Store approved credentials in deployment secret manager.
- Confirm purpose, legal basis, processing terms, quotas, and rate limits.
- Test positive, negative, conflicting, malformed, timeout, rate-limited, and unavailable outcomes with synthetic fixtures.
- Verify redaction, manual review, audit trail, retries, and circuit breaker behavior.
- Obtain staging approval before production activation.
