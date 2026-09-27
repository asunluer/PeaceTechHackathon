"""Store immutable capture artifacts with provenance and integrity hashes.

Revision ID: 20260926_03
Revises: 20260926_02
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260926_03"
down_revision = "20260926_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_artifacts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("submitted_link_id", sa.Uuid(as_uuid=True), sa.ForeignKey("submitted_links.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("captured_by", sa.String(length=100), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint("size_bytes >= 0 AND size_bytes <= 26214400", name="ck_evidence_artifacts_size"),
        sa.CheckConstraint("size_bytes = octet_length(payload)", name="ck_evidence_artifacts_payload_size"),
    )
    op.create_index("ix_evidence_artifacts_submitted_link_id", "evidence_artifacts", ["submitted_link_id"])
    op.execute("""
        CREATE FUNCTION reject_evidence_artifact_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'evidence artifacts are immutable';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER evidence_artifacts_immutable
        BEFORE UPDATE OR DELETE ON evidence_artifacts
        FOR EACH ROW EXECUTE FUNCTION reject_evidence_artifact_mutation()
    """)


def downgrade() -> None:
    op.drop_table("evidence_artifacts")
    op.execute("DROP FUNCTION reject_evidence_artifact_mutation()")
