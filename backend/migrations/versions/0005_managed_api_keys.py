"""Create managed API-key and security-event tables.

This revision is additive and portable across SQLite local tests and PostgreSQL.
Review the target schema before production use.
"""
from alembic import op
from src.database import Base
from src import models  # noqa: F401 - registers model metadata

revision = "0005_managed_api_keys"
down_revision = "0004_job_correlation_id"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = [
        Base.metadata.tables["managed_api_keys"],
        Base.metadata.tables["api_key_security_events"],
    ]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade():
    raise RuntimeError(
        "Managed API keys and security events are audit/security records. "
        "Use a reviewed forward migration; do not drop them automatically."
    )
