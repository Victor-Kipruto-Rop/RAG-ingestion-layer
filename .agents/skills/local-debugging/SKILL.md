---
name: local-debugging
description: Use when local services fail to start, cannot connect, return unhealthy status, or show upstream errors.
---

# Local Integration Debugging and Logs

## Diagnostic order
1. Capture the exact error and exit code, redacting secrets.
2. Confirm branch/working tree and configuration variable presence (never values).
3. Check Docker engine, container status, health checks, port conflicts, and Compose network.
4. Check database migrations and required local dependencies.
5. Test service liveness/readiness independently.
6. Verify URL selection from the caller's network namespace; distinguish host loopback from container loopback.
7. Verify API key configuration on both services without printing it.
8. Compare request/response schemas and inspect safe correlation IDs.
9. Classify the cause: environment, network, port, dependency, migration, authentication, authorization, contract, or code.
10. Make the smallest fix, add a regression test, and rerun the failing check.

## Guardrails
Never disable auth, TLS enforcement, validation, health checks, or rate limiting as a shortcut. Do not dump full environment variables or sensitive request bodies.
