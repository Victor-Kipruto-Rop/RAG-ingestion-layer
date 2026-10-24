---
name: repository-inspection
description: Use when working across the PesaGuard datasource and backend repositories. Inspect branches, working trees, architecture, contracts, and user changes before editing; preserve unrelated changes and keep patches minimal.
---

# Repository Inspection and Safe Changes

## When to use
Use before any multi-repository PesaGuard implementation, local integration, or debugging task.

## Workflow
1. Locate both repositories and verify the expected remotes.
2. Record current branch, commit, `git status --short`, and relevant diffs before editing.
3. Read repository instructions, README, relevant source, configuration, tests, and integration docs.
4. Verify the code actually checked out; do not assume prior summaries or documentation match current code.
5. Trace the call path and data contract before changing implementation.
6. Preserve user changes. Never reset, clean, force-push, or overwrite local work to simplify a task.
7. Make the smallest justified change and add a regression test.
8. Re-run targeted checks and inspect the final diff.

## Guardrails
- Do not refactor unrelated code.
- Do not invent endpoints, variables, models, or test outcomes.
- Do not commit or push unless explicitly requested.
- Report uncertainty and blockers with evidence.
