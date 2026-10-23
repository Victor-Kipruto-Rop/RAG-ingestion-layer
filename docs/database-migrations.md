# Alembic migration operations

Alembic is the forward path for schema changes. The repository contains an older SQL history in `database/migrations/` and Supabase-specific migration files. They are not automatically interchangeable with Alembic. Before making Alembic the only migration mechanism for an existing installation, reconcile all tables, columns, indexes, constraints, views, extensions, grants and row-level security policies against the target schema.

## Fresh disposable database

From `backend/` with dependencies installed and `DATABASE_URL` pointing only to a disposable database:

    python -m alembic -c alembic.ini upgrade head
    python -m alembic -c alembic.ini current

The bootstrap and schema-completion revisions create model-backed tables. On PostgreSQL, the completion revision also ensures `pg_trgm`, the trigram index used for fuzzy search, and the `warehouse_organizations` compatibility view exist. CI includes a disposable SQLite regression test that verifies all model-backed warehouse and API-key tables are present after `upgrade head`.

## Existing database — stop and reconcile first

Do not run `upgrade head` against an existing production database until a schema comparison has been reviewed. The original baseline revision creates missing tables, but it is not a complete schema-diff or repair engine for arbitrary missing columns and constraints.

After verifying that the deployed schema matches the expected baseline, a reviewed migration plan may use:

    python -m alembic -c alembic.ini stamp 0001_schema_bootstrap
    python -m alembic -c alembic.ini current

Stamping changes Alembic version metadata; it does not apply or validate the schema. Use only after a reviewed comparison, preferably first on a restored staging copy. Do not stamp a live warehouse as part of automated deployment.

## Future revisions

Generate a candidate in a development database, review the generated operations manually, and test upgrade and recovery on disposable copies. Do not use automatic metadata diffs as a substitute for review. Never place secrets in migration files or logs.

## Production change control

Migrations in this branch are code changes only. They have not been applied to Supabase or Render. Before any production change, take a provider-supported backup, verify restore procedures, compare the exact target schema, review lock/downtime impact, obtain explicit release-owner approval, and record the migration ID and verification evidence.
