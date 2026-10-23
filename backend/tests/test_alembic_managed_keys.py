import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_creates_managed_key_tables(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    database_path = tmp_path / "alembic-managed-keys.sqlite"
    database_url = f"sqlite:///{database_path.as_posix()}"
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
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
