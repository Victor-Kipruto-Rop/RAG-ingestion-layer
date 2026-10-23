"""Create environment-scoped customer API keys and audit events."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_environment_scoped_api_keys"
down_revision = "0004_job_correlation_id"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _create_api_keys(bind):
    if not sa.inspect(bind).has_table("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.String(36), primary_key=True, nullable=False),
            sa.Column("organization_id", sa.String(200), nullable=False),
            sa.Column("created_by_user_id", sa.String(200), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("environment", sa.String(20), nullable=False),
            sa.Column("key_prefix", sa.String(32), nullable=False),
            sa.Column("secret_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("scopes", _json_type(), nullable=False, server_default=sa.text("'[\"registry:read\"]'")),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_api_keys_environment"),
            sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_api_keys_status"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("api_keys")}
    if "ix_api_keys_org_created" not in indexes:
        op.create_index("ix_api_keys_org_created", "api_keys", ["organization_id", "created_at"])
    if "ix_api_keys_status_environment" not in indexes:
        op.create_index("ix_api_keys_status_environment", "api_keys", ["status", "environment"])


def _create_audit_events(bind):
    if not sa.inspect(bind).has_table("api_key_audit_events"):
        op.create_table(
            "api_key_audit_events",
            sa.Column("id", sa.String(36), primary_key=True, nullable=False),
            sa.Column("organization_id", sa.String(200), nullable=False),
            sa.Column("actor_user_id", sa.String(200), nullable=False),
            sa.Column("api_key_id", sa.String(36), nullable=True),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("details", _json_type(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("api_key_audit_events")}
    if "ix_api_key_audit_org_created" not in indexes:
        op.create_index("ix_api_key_audit_org_created", "api_key_audit_events", ["organization_id", "created_at"])


def upgrade():
    bind = op.get_bind()
    _create_api_keys(bind)
    _create_audit_events(bind)
    # Keep customer credentials and audit events out of Supabase client APIs.
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE api_key_audit_events ENABLE ROW LEVEL SECURITY")


def downgrade():
    raise RuntimeError("API-key and security audit history must be retained; use a reviewed forward migration.")
