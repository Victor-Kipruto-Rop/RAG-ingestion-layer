"""Persist operator accounts, email OTP challenges and revocable sessions."""
from alembic import op
import sqlalchemy as sa

revision = '0008_operator_auth_sessions'
down_revision = '0007_search_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admin_accounts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(320), nullable=False, unique=True),
        sa.Column('display_name', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_admin_accounts_email', 'admin_accounts', ['email'], unique=True)
    op.create_table(
        'admin_auth_challenges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('purpose', sa.String(32), nullable=False),
        sa.Column('otp_hash', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(120), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_admin_auth_challenges_email', 'admin_auth_challenges', ['email'])
    op.create_table(
        'admin_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(320), nullable=True),
        sa.Column('auth_method', sa.String(32), nullable=False, server_default='password'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('ip_digest', sa.String(64), nullable=True),
    )
    op.create_index('ix_admin_sessions_email', 'admin_sessions', ['email'])
    op.create_index('ix_admin_sessions_email', 'admin_sessions', ['email'])
    op.create_index('ix_admin_sessions_email_created', 'admin_sessions', ['email', 'created_at'])
    op.create_index('ix_admin_sessions_expiry', 'admin_sessions', ['expires_at'])


def downgrade():
    op.drop_index('ix_admin_sessions_expiry', table_name='admin_sessions')
    op.drop_index('ix_admin_sessions_email_created', table_name='admin_sessions')
    op.drop_index('ix_admin_sessions_email', table_name='admin_sessions')
    op.drop_index('ix_admin_sessions_email', table_name='admin_sessions')
    op.drop_table('admin_sessions')
    op.drop_index('ix_admin_auth_challenges_email', table_name='admin_auth_challenges')
    op.drop_table('admin_auth_challenges')
    op.drop_index('ix_admin_accounts_email', table_name='admin_accounts')
    op.drop_table('admin_accounts')
