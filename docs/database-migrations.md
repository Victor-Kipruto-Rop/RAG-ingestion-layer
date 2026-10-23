# Alembic migration operations

Alembic is the forward path for schema changes. The repository already has SQL migrations in database/migrations/001-005 and Supabase migrations; these histories must be reconciled before switching any existing database to Alembic.

## Fresh disposable database
From backend/ with dependencies installed and DATABASE_URL set to a disposable database:

    python -m alembic -c alembic.ini upgrade head
    python -m alembic -c alembic.ini current

The bootstrap revision creates the SQLAlchemy model schema for a fresh installation. It is intentionally not reversible.

## Existing database — stop and reconcile first
Do not run upgrade head against an existing production database until a schema comparison has been reviewed. Compare all tables, columns, indexes, constraints, views, extensions, grants and policies against model metadata and SQL/Supabase migration history. The baseline revision can then be stamped without executing it:

    python -m alembic -c alembic.ini stamp 0001_schema_bootstrap
    python -m alembic -c alembic.ini current

Stamping changes Alembic version metadata; it does not apply or validate the schema. Use only after reviewed comparison, preferably first on a restored staging copy. Do not stamp the live warehouse as part of automated deployment.

## Future revisions
Generate a candidate in a development database, review the generated operations manually, and test upgrade and recovery on disposable copies. Do not use automatic metadata diffs as a substitute for review. Never place secrets in migration files or logs.
