# PesaGuard Datasource Agent Skills

These are repository-local agent skills using the `.agents/skills/<skill-name>/SKILL.md` convention. Agents should load the relevant skill before doing related work and follow the main execution prompt at `prompts/run-local-connect-pesaguard.md`.

## Skills

1. [Repository Inspection and Safe Changes](repository-inspection/SKILL.md) — inspect code, branches, and diffs safely.
2. [Local Environment and Secret Management](local-env-secrets/SKILL.md) — create local-only `.env` files and protect secrets.
3. [Docker Compose Local Runtime](docker-local-runtime/SKILL.md) — validate Compose, ports, networks, and services.
4. [Datasource Health and Smoke Testing](datasource-health-smoke/SKILL.md) — verify readiness, auth, API, and smoke tests.
5. [PesaGuard Datasource Client Integration](backend-datasource-client/SKILL.md) — configure and test backend-to-datasource requests.
6. [Tenant Isolation and Authorization](tenant-authz-security/SKILL.md) — preserve tenant boundaries and permissions.
7. [Registry Lookup and Evidence-Only Semantics](registry-lookup-contract/SKILL.md) — enforce contract, privacy, and no automatic verification.
8. [Integration and Regression Testing](integration-regression-tests/SKILL.md) — test the end-to-end flow and failure paths.
9. [Local Integration Debugging and Logs](local-debugging/SKILL.md) — diagnose startup, networking, and API failures safely.
10. [Git Hygiene and Local Setup Documentation](git-hygiene-docs/SKILL.md) — keep secrets out of Git and document actual behavior.

## Rules

- Skills supplement the repository's main prompt and project instructions; they do not override them.
- Read the current code and configuration before relying on a skill's examples.
- Never report unexecuted checks as passing.
- Never commit local `.env` files, secrets, production data, or runtime artifacts.
