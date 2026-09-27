"""Drop AI analysis persistence; the feature was removed.

Revision ID: 20260927_05
Revises: 20260927_04
"""

from alembic import op
import sqlalchemy as sa

revision = "20260927_05"
down_revision = "20260927_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("ai_analyses")


def downgrade() -> None:
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("evidence_id", sa.Uuid(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("detected_threats", sa.JSON(), nullable=False),
        sa.Column("detected_pii", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("timeline", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_ai_analyses_evidence_id", "ai_analyses", ["evidence_id"])
    op.execute("CREATE TRIGGER ai_analyses_append_only BEFORE UPDATE OR DELETE ON ai_analyses FOR EACH ROW EXECUTE FUNCTION reject_record_mutation()")
