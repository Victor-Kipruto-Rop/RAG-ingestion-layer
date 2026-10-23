"""Create durable quality-review cases and append-only decisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_quality_review_cases"
down_revision = "0002_managed_api_keys"
branch_labels = None
depends_on = None


def _json_type():
    return postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("quality_review_cases"):
        op.create_table(
            "quality_review_cases",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("organization_id", sa.String(36), sa.ForeignKey("internal_organizations.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("related_organization_id", sa.String(36), sa.ForeignKey("internal_organizations.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("case_type", sa.String(40), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("severity", sa.String(20), nullable=False, server_default="review"),
            sa.Column("summary", sa.String(1000), nullable=False),
            sa.Column("evidence", _json_type(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_by", sa.String(200), nullable=False),
            sa.Column("assigned_to", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("case_type IN ('possible_duplicate','identifier_conflict','missing_data','stale_record','source_conflict','other')", name="ck_quality_review_case_type"),
            sa.CheckConstraint("status IN ('open','in_review','resolved','dismissed')", name="ck_quality_review_case_status"),
            sa.CheckConstraint("severity IN ('low','review','high')", name="ck_quality_review_case_severity"),
        )
    if not sa.inspect(bind).has_table("quality_review_decisions"):
        op.create_table(
            "quality_review_decisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("case_id", sa.String(36), sa.ForeignKey("quality_review_cases.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("decision", sa.String(40), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("evidence", _json_type(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("reviewer_ref", sa.String(200), nullable=False),
            sa.Column("request_id", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("decision IN ('same_entity','different_entities','needs_more_evidence','data_quality_issue','dismissed')", name="ck_quality_review_decision"),
        )
    for table, index, columns in [
        ("quality_review_cases", "ix_quality_review_cases_status_created", ["status", "created_at"]),
        ("quality_review_cases", "ix_quality_review_cases_org_created", ["organization_id", "created_at"]),
        ("quality_review_cases", "ix_quality_review_cases_type_status", ["case_type", "status"]),
        ("quality_review_decisions", "ix_quality_review_decisions_case_created", ["case_id", "created_at"]),
        ("quality_review_cases", "ix_quality_review_cases_organization_id", ["organization_id"]),
        ("quality_review_cases", "ix_quality_review_cases_related_organization_id", ["related_organization_id"]),
        ("quality_review_cases", "ix_quality_review_cases_status", ["status"]),
        ("quality_review_decisions", "ix_quality_review_decisions_case_id", ["case_id"]),
    ]:
        existing = {i["name"] for i in sa.inspect(bind).get_indexes(table)}
        if index not in existing:
            op.create_index(index, table, columns)


def downgrade():
    raise RuntimeError("Forward-only review history migration. Preserve review evidence; use a reviewed forward repair.")
