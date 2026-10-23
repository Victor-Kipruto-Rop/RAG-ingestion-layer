"""Create environment-scoped managed API keys and security-event tables.

This revision is intentionally forward-only. It tolerates tables already created
by the equivalent reviewed SQL migration (database/migrations/009_managed_api_keys.sql).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_managed_api_keys"
down_revision = "0001_schema_bootstrap"
branch_labels = None
depends_on = None


def _json_type():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("managed_api_keys"):
        op.create_table(
            "managed_api_keys",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("environment", sa.String(length=20), nullable=False),
            sa.Column("key_prefix", sa.String(length=80), nullable=False, unique=True),
            sa.Column("secret_hash", sa.String(length=64), nullable=False, unique=True),
            sa.Column("scopes", _json_type(), nullable=False, server_default=sa.text("'[]'")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_by", sa.String(length=120), nullable=False, server_default="operator"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rotated_from_id", sa.String(length=36), sa.ForeignKey("managed_api_keys.id")),
            sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_managed_api_keys_environment"),
            sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_managed_api_keys_status"),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("managed_api_keys"):
        indexes = {item["name"] for item in inspector.get_indexes("managed_api_keys")}
        if "ix_managed_api_keys_environment_status" not in indexes:
            op.create_index(
                "ix_managed_api_keys_environment_status",
                "managed_api_keys",
                ["environment", "status"],
            )
        if "ix_managed_api_keys_status" not in indexes:
            op.create_index("ix_managed_api_keys_status", "managed_api_keys", ["status"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("api_key_security_events"):
        op.create_table(
            "api_key_security_events",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("key_id", sa.String(length=36), nullable=True),
            sa.Column("key_prefix", sa.String(length=80), nullable=True),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("expected_environment", sa.String(length=20), nullable=True),
            sa.Column("key_environment", sa.String(length=20), nullable=True),
            sa.Column("endpoint", sa.String(length=300), nullable=True),
            sa.Column("http_method", sa.String(length=12), nullable=True),
            sa.Column("request_id", sa.String(length=100), nullable=True),
            sa.Column("client_ip", sa.String(length=80), nullable=True),
            sa.Column("details", _json_type(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    inspector = sa.inspect(bind)
    if inspector.has_table("api_key_security_events"):
        indexes = {item["name"] for item in inspector.get_indexes("api_key_security_events")}
        if "ix_api_key_security_events_created_at" not in indexes:
            op.create_index(
                "ix_api_key_security_events_created_at",
                "api_key_security_events",
                ["created_at"],
            )
        if "ix_api_key_security_events_key_id" not in indexes:
            op.create_index("ix_api_key_security_events_key_id", "api_key_security_events", ["key_id"])


def downgrade():
    raise RuntimeError(
        "Managed API-key schema is forward-only. Use a reviewed recovery plan; "
        "never drop credential audit history as an automated rollback."
    )
