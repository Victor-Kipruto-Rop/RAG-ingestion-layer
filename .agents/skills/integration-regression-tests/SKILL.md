---
name: integration-regression-tests
description: Use when verifying the end-to-end datasource-to-backend flow and running focused tests for changes.
---

# Integration and Regression Testing

## Workflow
1. Identify existing unit, route, smoke, and integration tests before adding new tests.
2. Run focused tests first, then compile/lint checks and the broader relevant suite.
3. Validate Compose configuration and actual service readiness.
4. Test the backend endpoint using a valid local user token and a local organization created through supported setup/fixtures.
5. Cover success, invalid auth, missing permission, cross-tenant denial, invalid input, upstream timeout/unavailability, malformed response, and no-match behavior.
6. Verify lookup does not change verification or activation state.
7. Do not use fake auth bypasses or mocks as proof of a real end-to-end connection.
8. Record exact commands and pass/fail/blocked results. Investigate relevant CI failures without unrelated refactoring.

## Reporting
Separate tests that passed from tests not run because of unavailable dependencies, credentials, or infrastructure.

undefined

## Mandatory quality gates
- For every test, state whether it is unit, integration, or end-to-end; do not conflate them.
- Never remove assertions, weaken expected status codes, skip failing tests without explicit justification, or replace integration tests with mocks to claim completion.
- Rerun the failing test after a fix and preserve its actual result.
- Mark unavailable infrastructure/credentials BLOCKED, not PASS. Include exact commands and outcomes.
