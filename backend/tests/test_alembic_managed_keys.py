import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def run_alembic(backend_dir, database_url, *args):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_alembic_upgrade_creates_managed_key_tables(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    database_path = tmp_path / "alembic-managed-keys.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"

    result = run_alembic(backend_dir, database_url, "upgrade", "head")
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert inspector.has_table("managed_api_keys")
        assert inspector.has_table("api_key_security_events")
        key_columns = {column["name"] for column in inspector.get_columns("managed_api_keys")}
        assert {"environment", "key_prefix", "secret_hash", "scopes", "expires_at", "revoked_at"} <= key_columns
        event_columns = {column["name"] for column in inspector.get_columns("api_key_security_events")}
        assert {"event_type", "expected_environment", "key_environment", "request_id"} <= event_columns
    finally:
        engine.dispose()


def test_alembic_upgrade_tolerates_tables_from_the_sql_migration(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    database_path = tmp_path / "alembic-existing-keys.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"

    bootstrap = run_alembic(backend_dir, database_url, "upgrade", "0001_schema_bootstrap")
    assert bootstrap.returncode == 0, bootstrap.stdout + "\n" + bootstrap.stderr

    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("""
                CREATE TABLE managed_api_keys (
                    id varchar(36) PRIMARY KEY,
                    name varchar(120) NOT NULL,
                    environment varchar(20) NOT NULL,
                    key_prefix varchar(80) NOT NULL UNIQUE,
                    secret_hash varchar(64) NOT NULL UNIQUE,
                    scopes JSON NOT NULL DEFAULT '[]',
                    status varchar(20) NOT NULL DEFAULT 'active',
                    created_by varchar(120) NOT NULL DEFAULT 'operator',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_used_at DATETIME,
                    expires_at DATETIME,
                    revoked_at DATETIME,
                    rotated_from_id varchar(36)
                )
            """)
            connection.exec_driver_sql("""
                CREATE INDEX ix_managed_api_keys_environment_status
                ON managed_api_keys(environment, status)
            """)
            connection.exec_driver_sql("""
                CREATE TABLE api_key_security_events (
                    id varchar(36) PRIMARY KEY,
                    key_id varchar(36),
                    key_prefix varchar(80),
                    event_type varchar(80) NOT NULL,
                    expected_environment varchar(20),
                    key_environment varchar(20),
                    endpoint varchar(300),
                    http_method varchar(12),
                    request_id varchar(100),
                    client_ip varchar(80),
                    details JSON NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.exec_driver_sql("""
                CREATE INDEX ix_api_key_security_events_created_at
                ON api_key_security_events(created_at)
            """)
            connection.exec_driver_sql("""
                CREATE INDEX ix_api_key_security_events_key_id
                ON api_key_security_events(key_id)
            """)
    finally:
        engine.dispose()

    upgraded = run_alembic(backend_dir, database_url, "upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stdout + "\n" + upgraded.stderr

    engine = create_engine(database_url)
    try:
        indexes = {item["name"] for item in inspect(engine).get_indexes("managed_api_keys")}
        assert "ix_managed_api_keys_environment_status" in indexes
        assert "ix_managed_api_keys_status" in indexes
    finally:
        engine.dispose()
