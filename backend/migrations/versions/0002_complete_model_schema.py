"""Complete model-backed schema for fresh and reconciled installations.

This forward revision fills any model tables omitted by the original bootstrap.
It does not attempt to repair arbitrary missing columns in an existing database;
compare and reconcile an existing schema before applying it.
"""
from alembic import op
from sqlalchemy import text

from src.database import Base
from src import models  # noqa: F401 - registers all model metadata

revision = "0002_complete_model_schema"
down_revision = "0001_schema_bootstrap"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Required by the PostgreSQL trigram similarity fallback used by registry search.
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Use the model registry as the source for table coverage. checkfirst keeps
    # this additive for a clean database and a schema that was reviewed/stamped.
    Base.metadata.create_all(bind=bind, checkfirst=True)

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_internal_organizations_name_trgm "
            "ON internal_organizations USING gin (normalized_legal_name gin_trgm_ops)"
        )
        op.execute(text("""
            CREATE OR REPLACE VIEW warehouse_organizations AS
            SELECT id, legal_name, normalized_legal_name,
                   registration_number, normalized_registration_number,
                   tax_pin, normalized_tax_pin, status, registry_payload,
                   source_file, source_row, source_name, source_record_id,
                   source_published_at, last_seen_at, data_quality_status,
                   created_at, updated_at
            FROM internal_organizations
        """))


def downgrade():
    raise RuntimeError(
        "This schema-completion migration is forward-only. Use a reviewed "
        "restore or forward repair; do not drop warehouse tables during rollback."
    )
