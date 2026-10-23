"""Initial schema bootstrap for fresh installations.

Existing installations created from database/migrations/001-005 must be schema-
reconciled and stamped to this revision; do not blindly run this revision on
production. Future schema changes must use explicit, forward-only Alembic revisions.
"""
from alembic import op
from src.database import Base
from src import models  # noqa: F401

revision = '0001_schema_bootstrap'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Bootstrap only: create missing tables for a clean installation.
    # Existing deployments should stamp this revision only after schema comparison.
    bootstrap_tables = ('internal_organizations', 'organization_record_versions', 'registry_sources', 'ingestion_jobs', 'ingestion_row_errors', 'ingestion_audit_logs', 'warehouse_raw_imports', 'warehouse_access_logs')
    tables = [Base.metadata.tables[name] for name in bootstrap_tables if name in Base.metadata.tables]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables, checkfirst=True)

def downgrade():
    raise RuntimeError('The baseline migration is intentionally irreversible. Use a reviewed forward migration; never drop the production schema.')
