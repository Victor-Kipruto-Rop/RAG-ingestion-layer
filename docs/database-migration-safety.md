# Database migration safety

## Current migration sources

This repository has SQL migration files under `database/migrations/` and an Alembic configuration under `backend/alembic.ini`. Treat them as two migration histories until their equivalence and ordering have been explicitly reconciled. Do not assume an Alembic revision number matches a SQL filename.

## Required safeguards

- Never run a schema migration automatically at application startup.
- Never apply migrations to production as part of a normal pull request or CI job.
- Never use Alembic `stamp` to make a database appear migrated before verifying its actual schema.
- Never apply a SQL migration and an Alembic revision that make the same change twice unless both are proven idempotent and intended for that database.
- Before any production change, identify the actual deployed schema, compare it with both histories, and prepare a backup/restore plan.
- Test a clean bootstrap and an upgrade from a schema snapshot matching the deployed database.
- Test against a disposable database first. CI's SQLite migration smoke test does not prove PostgreSQL/Supabase compatibility.
- Keep credentials out of migration output and use a least-privilege migration role where feasible.

## Proposed reconciliation process

1. Inventory all files in `database/migrations/` and `backend/migrations/versions/`.
2. For each SQL file, identify the equivalent Alembic revision (if one exists) and compare the actual DDL.
3. Create a mapping table of SQL filename, Alembic revision, deployed status, and schema objects changed.
4. Inspect the deployed schema read-only and compare it with the expected end state.
5. Select one canonical migration path for future changes only after the owner approves the mapping.
6. Add an explicit baseline/bridge migration only after testing against a production-like snapshot.
7. Document the chosen path and remove neither historical files nor revision records until the transition is verified.

## Verification checklist

- [ ] Primary keys, unique constraints, foreign keys, check constraints, and indexes match the intended model.
- [ ] JSON/JSONB and timestamp types behave correctly on PostgreSQL.
- [ ] New columns have safe defaults or a documented backfill plan.
- [ ] Existing rows remain readable and no duplicate identifiers violate constraints.
- [ ] API/worker versions are compatible with the pre- and post-migration schemas during rollout.
- [ ] Backup restoration has been tested in an isolated environment.
- [ ] The release record contains the exact applied migration identifiers.

A green SQLite smoke test is useful but insufficient as the only evidence for a production PostgreSQL migration.