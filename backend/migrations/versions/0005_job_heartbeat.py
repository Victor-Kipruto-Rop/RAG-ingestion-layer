"""Add a worker heartbeat so long-running jobs are not recovered as stale."""
import sqlalchemy as sa
from alembic import op

revision = '0005_job_heartbeat'
down_revision = '0004_job_correlation_id'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column['name'] for column in inspector.get_columns('ingestion_jobs')}
    if 'heartbeat_at' not in columns:
        op.add_column('ingestion_jobs', sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True))
    indexes = {index['name'] for index in inspector.get_indexes('ingestion_jobs')}
    if 'ix_ingestion_jobs_status_next_attempt' not in indexes:
        op.create_index('ix_ingestion_jobs_status_next_attempt', 'ingestion_jobs', ['status', 'next_attempt_at'])


def downgrade():
    raise RuntimeError('Heartbeat data protects running jobs; use a reviewed forward migration.')
