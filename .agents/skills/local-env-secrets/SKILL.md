---
name: local-env-secrets
description: Use when generating or updating local .env files, configuring service keys, database URLs, JWT secrets, or encryption keys. Prevents production secret leakage.
---

# Local Environment and Secret Management

## Workflow
1. Inspect `.env.example`, configuration loaders, Compose files, and `.gitignore`.
2. Never overwrite an existing `.env` wholesale. Create it from the example only if absent.
3. Confirm `.env`, local databases, uploaded files, and generated credentials are ignored by Git before writing secrets.
4. Generate local secrets with a cryptographically secure operating-system random generator. Follow the exact format required by the application.
5. Keep datasource API keys server-side only. Configure the same local-only key in the datasource and PesaGuard backend.
6. Use local databases and development endpoints; never copy production secrets or customer data.
7. Keep examples sanitized. Put placeholders, not actual secret values, in `.env.example`.
8. Avoid printing secrets in terminal commands, test output, logs, screenshots, or final reports.
9. Inspect `git status --short` and the staged diff before finishing.

## Completion criteria
Report variable names and whether they are configured, never their values. If a required secret is missing, identify it without fabricating a credential.

undefined

undefined

## Mandatory quality gates
- Check ignore rules before creating a secret-bearing file; if inadequate, fix them first.
- Preserve existing local values and do not echo secrets while inspecting or editing.
- Confirm secret formats against the actual config parser. Never invent encryption-key formats or silently substitute defaults.
- Scan tracked diffs for secrets and ensure only sanitized placeholders appear in examples.
- If a real credential is required, mark that integration step BLOCKED; never use production credentials as a workaround.
