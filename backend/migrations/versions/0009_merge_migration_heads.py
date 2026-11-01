"""Merge the developer control-plane and operator-auth migration branches."""

revision = '0009_merge_migration_heads'
down_revision = (
    '0002_developer_control_plane',
    '0003_operator_profile_notifications',
    '0008_operator_auth_sessions',
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
