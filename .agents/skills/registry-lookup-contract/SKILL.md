---
name: registry-lookup-contract
description: Use when implementing or testing the organization registry lookup endpoint and its request/response behavior.
---

# Registry Lookup and Evidence-Only Semantics

## Workflow
1. Inspect the current datasource and backend request/response schemas before changing code.
2. Confirm accepted lookup fields, validation rules, provenance metadata, and not-found behavior.
3. Keep the lookup read-only and evidence-only. It must not automatically verify, approve, reject, activate, or change onboarding state.
4. Return only fields required by the authenticated client. Remove tax PINs and raw registry payloads from browser-facing responses where the current contract requires it.
5. Distinguish no match, invalid request, upstream unavailable, timeout, malformed upstream response, and internal error.
6. Never invent registry results or imply that imported data is an official government verification.
7. Use fictional test identifiers and locally seeded test records for tests.
8. Test that the organization's verification status is unchanged before and after lookup.

## Acceptance
Contract tests must prove the request shape, response validation, safe error mapping, sensitive-field filtering, and no verification-state mutation.

undefined

## Mandatory quality gates
- Validate schema and provenance; reject missing, unexpected, or malformed values safely.
- Test organization verification state before and after lookup and prove lookup is read-only.
- Filter sensitive values from responses and logs according to the current contract.
- Never infer official verification from a lookup, fixture, vendor outage, or no-match response.
