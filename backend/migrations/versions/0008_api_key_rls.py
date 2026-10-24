"""Force tenant scoping for customer API key and key-audit records on PostgreSQL."""
from alembic import op
from sqlalchemy import text

revision = "0008_api_key_rls"
down_revision = "0007_search_indexes"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite is used for fast local tests; PostgreSQL CI/staging validates real RLS.
        return
    for table in ("api_keys", "api_key_audit_events"):
        bind.execute(text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        bind.execute(text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        bind.execute(text(
            f'DROP POLICY IF EXISTS "{table}_tenant_isolation" ON "{table}"'
        ))
        bind.execute(text(
            f'''CREATE POLICY "{table}_tenant_isolation" ON "{table}"
                USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''))
                WITH CHECK (organization_id = NULLIF(current_setting('app.current_org_id', true), ''))'''
        ))


def downgrade():
    raise RuntimeError("Tenant RLS is a security boundary; use a reviewed forward migration.")
