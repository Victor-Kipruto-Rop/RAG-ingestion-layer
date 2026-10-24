---
name: tenant-authz-security
description: Use when working on organization-scoped endpoints, PesaGuard authentication, permission checks, or tenant isolation.
---

# Tenant Isolation and Authorization

## Workflow
1. Trace the existing authentication middleware, authorization/permission checks, tenant context, and organization lookup patterns.
2. Derive tenant identity from trusted authenticated server context, not from caller-supplied tenant IDs.
3. Confirm the requested organization belongs to the authenticated tenant before any lookup.
4. Apply the existing least-privilege permission required by the route (verify the current code; do not assume a permission name).
5. Reject missing/invalid credentials, insufficient permissions, malformed identifiers, and cross-tenant access.
6. Add regression tests for each rejection path.
7. Ensure error responses do not leak whether another tenant's organization exists or expose sensitive data.
8. Do not create production auth bypasses or weaken authorization for local testing.

## Required invariant
A user in tenant A must not read or mutate tenant B's organization or evidence.
