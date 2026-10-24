---
name: git-hygiene-docs
description: Use when documenting local PesaGuard integration, reviewing diffs, or preparing changes for commit.
---

# Git Hygiene and Local Setup Documentation

## Workflow
1. Keep local `.env`, generated keys, runtime databases, uploaded files, logs, and test artifacts out of Git.
2. Ensure `.env.example` contains placeholders only.
3. Document actual prerequisites, ports, URLs, start/stop commands, health checks, and test commands.
4. Align README, scripts, Compose mappings, and integration docs whenever local port/network configuration changes.
5. Inspect `git diff --check`, `git status --short`, and the complete diff.
6. Search the diff for likely secrets, tokens, passwords, real identifiers, and local artifacts before finishing.
7. Preserve unrelated user changes and do not stage broad directory changes.
8. Do not commit, push, or open/merge a pull request unless explicitly asked.

## Final report
List changed paths, commands actually run, test results, service health, remaining blockers, and security checks. Never say CI passed without checking current CI results.
