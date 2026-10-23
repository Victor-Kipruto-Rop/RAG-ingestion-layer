"""Create environment-isolated managed API key tables.

Revision ID: 20261023_managed_api_keys
Revises:
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261023_managed_api_keys"
down_revision = None
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade():
    op.create_table(
        "managed_api_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("environment", sa.String(length=20), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False, unique=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", _json_type(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(length=100), nullable=False, server_default="service-operator"),
        sa.Column("rotated_from_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_managed_api_keys_environment"),
        sa.CheckConstraint("status IN ('active', 'revoked', 'expired')", name="ck_managed_api_keys_status"),
    )
    op.create_index("ix_managed_api_keys_environment", "managed_api_keys", ["environment"])
    op.create_index("ix_managed_api_keys_status", "managed_api_keys", ["status"])
    op.create_index("ix_managed_api_keys_environment_status", "managed_api_keys", ["environment", "status"])
    op.create_table(
        "api_key_security_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key_id", sa.String(length=36), nullable=True),
        sa.Column("key_prefix", sa.String(length=32), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("requested_environment", sa.String(length=20), nullable=False),
        sa.Column("endpoint", sa.String(length=300), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_key_security_events_key_id", "api_key_security_events", ["key_id"])
    op.create_index("ix_api_key_security_events_event_type", "api_key_security_events", ["event_type"])
    op.create_index("ix_api_key_events_created_at", "api_key_security_events", ["created_at"])


def downgrade():
    op.drop_index("ix_api_key_events_created_at", table_name="api_key_security_events")
    op.drop_index("ix_api_key_security_events_event_type", table_name="api_key_security_events")
    op.drop_index("ix_api_key_security_events_key_id", table_name="api_key_security_events")
    op.drop_table("api_key_security_events")
    op.drop_index("ix_managed_api_keys_environment_status", table_name="managed_api_keys")
    op.drop_index("ix_managed_api_keys_status", table_name="managed_api_keys")
    op.drop_index("ix_managed_api_keys_environment", table_name="managed_api_keys")
    op.drop_table("managed_api_keys")
