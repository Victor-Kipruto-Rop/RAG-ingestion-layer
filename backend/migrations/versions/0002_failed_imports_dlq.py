"""Create restricted dead-letter storage for invalid ingestion rows."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0002_failed_imports_dlq'
down_revision = '0001_schema_bootstrap'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if sa.inspect(bind).has_table('failed_imports_dlq'):
        return
    json_type = sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')
    op.create_table('failed_imports_dlq',
        sa.Column('id', sa.String(36), primary_key=True, nullable=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('ingestion_jobs.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('error_code', sa.String(80), nullable=False),
        sa.Column('error_type', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sanitized_row', json_type, nullable=False),
        sa.Column('traceback_text', sa.Text(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('job_id', 'row_number', 'error_code', name='uq_failed_import_job_row_code'))
    op.create_index('ix_failed_imports_dlq_job_id', 'failed_imports_dlq', ['job_id'])
    op.create_index('ix_failed_imports_dlq_created_at', 'failed_imports_dlq', ['created_at'])

def downgrade():
    raise RuntimeError('DLQ data is audit evidence; use a reviewed retention migration rather than dropping it.')
