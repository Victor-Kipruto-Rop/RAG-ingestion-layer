"""Alembic and the SQL migration files must both produce exactly the schema the models define."""
import os
import pathlib

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from src.database import Base
from src import models  # noqa: F401

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def _alembic_config():
    config = Config(str(BACKEND / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND / 'migrations'))
    return config


def _model_columns():
    return {table.name: {column.name for column in table.columns} for table in Base.metadata.tables.values()}


def _db_columns(engine):
    inspector = sa.inspect(engine)
    return {name: {column['name'] for column in inspector.get_columns(name)} for name in inspector.get_table_names() if name != 'alembic_version'}


def _assert_matches_models(actual, label):
    expected = _model_columns()
    missing_tables = sorted(set(expected) - set(actual))
    assert not missing_tables, f'{label}: tables missing {missing_tables}'
    for table, columns in expected.items():
        assert columns <= actual[table], f'{label}: {table} is missing columns {sorted(columns - actual[table])}'
        assert actual[table] <= columns, f'{label}: {table} has columns the models do not define: {sorted(actual[table] - columns)}'


def test_alembic_upgrade_head_matches_models_on_sqlite(tmp_path, monkeypatch):
    url = f'sqlite:///{tmp_path}/alembic.db'
    monkeypatch.setenv('DATABASE_URL', url)
    command.upgrade(_alembic_config(), 'head')
    _assert_matches_models(_db_columns(sa.create_engine(url)), 'alembic/sqlite')
    command.upgrade(_alembic_config(), 'head')  # re-running must be a no-op


PG_ADMIN_URL = os.environ.get('TEST_PG_ADMIN_URL')
pg = pytest.mark.skipif(not PG_ADMIN_URL, reason='set TEST_PG_ADMIN_URL (superuser, e.g. postgresql+psycopg://u:p@host/postgres) to run PostgreSQL migration tests')


@pytest.fixture
def pg_database():
    import uuid
    admin = sa.create_engine(PG_ADMIN_URL, isolation_level='AUTOCOMMIT')
    name = 'migtest_' + uuid.uuid4().hex[:10]
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE {name}'))
        for role in ('anon', 'authenticated', 'service_role'):
            conn.execute(sa.text(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN CREATE ROLE {role} NOLOGIN; END IF; END $$"))
    url = sa.engine.make_url(PG_ADMIN_URL).set(database=name)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)'))
        admin.dispose()


def _apply_sql_files(engine, folder):
    for path in sorted(folder.glob('*.sql')):
        with engine.connect() as conn:
            conn.exec_driver_sql(path.read_text().replace('%', '%%'))
            conn.commit()


@pg
def test_sql_migrations_produce_the_model_schema_and_lock_down_browser_roles(pg_database):
    engine = sa.create_engine(pg_database)
    _apply_sql_files(engine, ROOT / 'database' / 'migrations')
    _assert_matches_models(_db_columns(engine), 'database/migrations')
    with engine.connect() as conn:
        rls = dict(conn.execute(sa.text("SELECT relname, relrowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind='r'")).all())
        for table in _model_columns():
            assert rls[table] is True, f'row level security is not enabled on {table}'
        grants = conn.execute(sa.text("SELECT table_name, grantee FROM information_schema.role_table_grants WHERE grantee IN ('anon','authenticated') AND table_schema='public'")).all()
        assert grants == [], f'browser roles still have table privileges: {grants}'
        indexes = {row[0] for row in conn.execute(sa.text("SELECT indexname FROM pg_indexes WHERE schemaname='public'"))}
        assert {'ix_org_normalized_name_trgm', 'ix_ingestion_jobs_status_next_attempt'} <= indexes
    # re-applying must be safe (idempotent)
    _apply_sql_files(engine, ROOT / 'database' / 'migrations')
    engine.dispose()


@pg
def test_alembic_upgrade_head_matches_models_on_postgresql(pg_database, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', pg_database.render_as_string(hide_password=False))
    command.upgrade(_alembic_config(), 'head')
    engine = sa.create_engine(pg_database)
    _assert_matches_models(_db_columns(engine), 'alembic/postgresql')
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT 1 FROM pg_indexes WHERE indexname='ix_org_normalized_name_trgm'")).scalar() == 1
    engine.dispose()


@pg
def test_supabase_migrations_apply_on_top_of_the_core_schema(pg_database):
    engine = sa.create_engine(pg_database)
    _apply_sql_files(engine, ROOT / 'database' / 'migrations')
    for path in sorted((ROOT / 'supabase' / 'migrations').glob('*.sql')):
        with engine.connect() as conn:
            conn.exec_driver_sql(path.read_text().replace('%', '%%'))
            conn.commit()
    _assert_matches_models(_db_columns(engine), 'supabase/migrations after core schema')
    engine.dispose()
