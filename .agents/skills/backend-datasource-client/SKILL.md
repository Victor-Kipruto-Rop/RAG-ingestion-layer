---
name: backend-datasource-client
description: Use when connecting the PesaGuard backend server-side client to the registry datasource and validating network URLs, request contracts, timeouts, and safe errors.
---

# PesaGuard Datasource Client Integration

## Workflow
1. Inspect `registry_datasource_client.py`, datasource route definitions, settings loader, dependency wiring, and tests.
2. Confirm the exact method, path, request fields, authentication header, response schema, and error mapping on both sides.
3. Configure the datasource base URL and key in backend server environment only.
4. Use bounded connect/read timeouts and validate all response fields before returning data.
5. Preserve correlation/request IDs where supported; never include credentials in logs or client-visible errors.
6. Allow local HTTP only in explicit development/test configurations and only for approved local hosts. Production must retain HTTPS enforcement.
7. Add tests for valid response, timeout, connection error, invalid JSON/schema, authentication failure, and upstream error responses.
8. Verify the backend can reach the datasource from its actual runtime network; a URL working in the host browser does not prove container reachability.

## Guardrails
Do not place the service key in frontend configuration. Do not replace real network behavior with a mock and call that end-to-end proof.
