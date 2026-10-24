---
name: datasource-health-smoke
description: Use when verifying local datasource startup, health endpoints, protected API behavior, and the datasource integration smoke test.
---

# Datasource Health and Smoke Testing

## Workflow
1. Read the datasource README, Compose configuration, route definitions, and existing smoke-test script.
2. Start the service using the supported local script.
3. Check liveness and readiness endpoints separately; readiness should reflect required dependencies.
4. Check API docs and dashboard on the actual configured ports.
5. Run the existing smoke test with the local API key supplied via environment variables, not hard-coded in source.
6. Test valid authentication, missing/invalid key, malformed input, no matching local record, and dependency-unavailable behavior where feasible.
7. Use fictional identifiers and local data only.
8. Distinguish a successful local lookup from a verified external government/vendor integration.

## Evidence
Record actual command exit codes, HTTP status, and service health. Redact credentials and sensitive payloads. Never claim success if a check was skipped or blocked.
