"""Persist CSV row progress for safe batch commits and retry resume."""
import sqlalchemy as sa
from alembic import op

revision = '0003_ingestion_row_progress'
down_revision = '0002_failed_imports_dlq'
branch_labels = None
depends_on = None

def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('ingestion_jobs')}
    if 'last_processed_row' not in columns:
        op.add_column('ingestion_jobs', sa.Column('last_processed_row', sa.Integer(), nullable=False, server_default='1'))

def downgrade():
    raise RuntimeError('Row progress is required for safe ingestion resume; use a reviewed forward migration.')
