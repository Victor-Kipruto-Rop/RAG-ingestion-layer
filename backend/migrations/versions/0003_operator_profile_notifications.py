"""Add operator profile and notification read state."""
import sqlalchemy as sa
from alembic import op

revision = '0003_operator_profile_notifications'
down_revision = '0002_failed_imports_dlq'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('admin_profiles'):
        op.create_table(
            'admin_profiles',
            sa.Column('id', sa.String(36), primary_key=True, nullable=False),
            sa.Column('display_name', sa.String(120), nullable=False, server_default='Datasource Operator'),
            sa.Column('contact_email', sa.String(320), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
    if not inspector.has_table('admin_notification_reads'):
        op.create_table(
            'admin_notification_reads',
            sa.Column('notification_key', sa.String(300), primary_key=True, nullable=False),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=False),
        )


def downgrade():
    op.drop_table('admin_notification_reads')
    op.drop_table('admin_profiles')
