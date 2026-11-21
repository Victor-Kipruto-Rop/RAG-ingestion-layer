# Registry datasource on the PesaGuard VPS

The production Compose file replaces the local SQLite database with PostgreSQL and uses the existing private Cloudflare R2 integration for uploaded registry files. PostgreSQL, Redis, registry API and operator frontend publish no host ports. The API is attached to the operations project's dedicated internal proxy network and reaches the registry API over TLS at https://registry.pesaguard.co.ke. The same hostname serves the operator SPA at / and routes /api/ to the registry API.

## Configure

1. Copy backend/.env.production.example to backend/.env.production.
2. Configure a private R2 bucket in the approved data-residency jurisdiction.
3. Set a unique database password and service API key.
4. Put the exact same service API key in operations .env.production as PESAGUARD_DATASOURCE_API_KEY.
5. Keep backend/.env.production mode 600 and out of Git.
6. Set admin OAuth/signup allowlists; do not create a default admin password.

## Start after the core PesaGuard stack creates the shared network

    docker compose --env-file backend/.env.production -f docker-compose.production.yml -p pesaguard-registry config
    docker compose --env-file backend/.env.production -f docker-compose.production.yml -p pesaguard-registry up -d --build
    docker compose --env-file backend/.env.production -f docker-compose.production.yml -p pesaguard-registry ps

The registry API readiness probe requires PostgreSQL, Redis and a reachable R2 bucket. The operator frontend is built with the same-origin HTTPS API base. The worker shares the same database and upload volume.

## Security and scope

- Only the core API should call registry-api through the private Docker network.
- Keep the R2 bucket private; do not expose its console or credentials.
- Use the imported records as read-only evidence. This is not a live KRA/BRS integration and must not auto-approve tax PINs.
- Back up PostgreSQL and R2 objects independently. The operations VPS backup script does not yet include this database or R2 bucket.
- Do not enable HMAC request enforcement until the API client signs the exact canonical request contract.
