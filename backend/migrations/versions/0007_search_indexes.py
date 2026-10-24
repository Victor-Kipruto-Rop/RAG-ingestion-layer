"""PostgreSQL trigram index so substring and fuzzy name search do not scan the table."""
from alembic import op

revision = '0007_search_indexes'
down_revision = '0006_api_key_tables'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute('CREATE INDEX IF NOT EXISTS ix_org_normalized_name_trgm ON internal_organizations USING gin (normalized_legal_name gin_trgm_ops)')


def downgrade():
    raise RuntimeError('Use a reviewed forward migration to change search indexes.')
