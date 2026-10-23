"""Persist request correlation IDs on ingestion jobs."""
import sqlalchemy as sa
from alembic import op

revision = '0004_job_correlation_id'
down_revision = '0003_ingestion_row_progress'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('ingestion_jobs')}
    if 'correlation_id' not in columns:
        op.add_column('ingestion_jobs', sa.Column('correlation_id', sa.String(length=100), nullable=True))
    indexes = {index['name'] for index in sa.inspect(bind).get_indexes('ingestion_jobs')}
    if 'ix_ingestion_jobs_correlation_id' not in indexes:
        op.create_index('ix_ingestion_jobs_correlation_id', 'ingestion_jobs', ['correlation_id'])

def downgrade():
    raise RuntimeError('Correlation IDs are operational audit context; use a reviewed forward migration.')
