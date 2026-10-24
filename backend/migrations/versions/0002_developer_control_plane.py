"""Create isolated developer control-plane tables.

Existing production databases must review their current schema and migration stamp before
applying this revision. This revision creates only developer-platform tables.
"""
from alembic import op
from src.database import Base
from src import models  # noqa: F401

revision = '0002_developer_control_plane'
down_revision = '0001_schema_bootstrap'
branch_labels = None
depends_on = None

TABLES = (
    'developer_accounts',
    'developer_workspaces',
    'developer_projects',
    'developer_auth_challenges',
    'developer_sessions',
    'developer_webhooks',
    'developer_webhook_deliveries',
    'developer_production_access_requests',
)

def upgrade():
    bind = op.get_bind()
    selected = [Base.metadata.tables[name] for name in TABLES]
    Base.metadata.create_all(bind=bind, tables=selected, checkfirst=True)

def downgrade():
    raise RuntimeError('Developer control-plane migration is forward-only; disable access and use a reviewed data-retention plan instead of dropping production identity data.')
