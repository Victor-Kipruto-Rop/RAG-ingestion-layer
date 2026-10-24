# Prompt Index

Read the matching prompt and relevant repository skills before execution. The Strict Prompt and Agent Execution Standard applies to every prompt and skill.

## Available prompts
- [Run datasource locally and connect it to PesaGuard](run-local-connect-pesaguard.md) — local-only environment setup, service startup, authenticated integration, tests, and evidence-based reporting.
- [Strict Prompt and Agent Execution Standard](STRICT_PROMPT_STANDARD.md) — mandatory safety, verification, scope, and reporting rules.

## Execution requirements
- Work on the intended branch and preserve all existing user changes.
- Never print or commit secrets.
- Do not deploy or modify production resources unless separately authorized.
- Treat checklists as release gates, not suggestions.
- Report unexecuted checks as NOT RUN or BLOCKED, never as passed.