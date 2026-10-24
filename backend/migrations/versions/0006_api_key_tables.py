"""Create customer API key tables for installations bootstrapped through Alembic."""
import sqlalchemy as sa
from alembic import op

from src.database import Base
from src import models  # noqa: F401

revision = '0006_api_key_tables'
down_revision = '0005_job_heartbeat'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    tables = [Base.metadata.tables[name] for name in ('api_keys', 'api_key_audit_events') if name not in existing]
    if tables:
        Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade():
    raise RuntimeError('API key records are security evidence; use a reviewed forward migration.')
