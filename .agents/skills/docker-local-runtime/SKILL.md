---
name: docker-local-runtime
description: Use when building, starting, stopping, or troubleshooting PesaGuard datasource and backend services locally with Docker Compose.
---

# Docker Compose Local Runtime

## Workflow
1. Confirm Docker CLI and engine are available.
2. Inspect Compose files, service names, ports, networks, volumes, health checks, and required environment variables.
3. Validate configuration before startup with the repository's supported Compose command.
4. Check host port availability. Avoid port collisions; if datasource host port 8000 conflicts with the backend, publish datasource container port 8000 on a free host port such as 8010 and update local docs/tests.
5. Choose URLs based on network topology:
   - Host process to published container: `127.0.0.1:<published-port>`.
   - Container to host-published service: `host.docker.internal:<published-port>` where supported and allowed.
   - Containers on one Docker network: Compose service DNS and container port.
6. Build and start only required local services.
7. Inspect container health and redacted logs. Never print secret environment values.
8. Stop services using documented scripts; do not delete volumes or reset databases without explicit approval.

## Guardrails
Never point local containers at production databases or services. Do not remove health checks or security controls to force startup.

undefined

## Mandatory quality gates
- Validate effective Compose configuration before building/starting services; do not expose rendered secret values.
- Check port availability and network paths before changing mappings.
- Never use destructive volume deletion, database reset, broad prune, or cleanup commands without explicit approval.
- Distinguish container-running from healthy/readiness-confirmed. Capture service-specific evidence.
- If a service fails, diagnose the root cause and rerun affected checks after the fix.
