import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def test_alembic_upgrade_creates_all_security_and_warehouse_tables(tmp_path):
    database_path = tmp_path / "migration-check.sqlite"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env.pop("APP_ENV", None)

    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, (
        f"Alembic upgrade failed. stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
    )

    engine = create_engine(env["DATABASE_URL"])
    try:
        tables = set(inspect(engine).get_table_names())
        required = {
            "internal_organizations",
            "organization_record_versions",
            "registry_sources",
            "ingestion_jobs",
            "ingestion_row_errors",
            "ingestion_audit_logs",
            "warehouse_raw_imports",
            "warehouse_access_logs",
            "failed_imports_dlq",
            "managed_api_keys",
            "api_key_security_events",
        }
        assert required.issubset(tables), f"Missing tables after Alembic upgrade: {sorted(required - tables)}"
        assert "alembic_version" in tables
    finally:
        engine.dispose()
