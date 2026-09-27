"""Complete case, evidence, analysis, and audit persistence.

Revision ID: 20260927_04
Revises: 20260926_03
"""

from alembic import op
import sqlalchemy as sa

revision = "20260927_04"
down_revision = "20260926_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("victim_statement", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("status", sa.String(20), server_default="open", nullable=False))
    op.add_column("cases", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.add_column("submitted_links", sa.Column("shared_text", sa.Text(), nullable=True))
    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("case_id", sa.Uuid(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_link_id", sa.Uuid(as_uuid=True), sa.ForeignKey("submitted_links.id", ondelete="RESTRICT"), unique=True, nullable=False),
        sa.Column("platform", sa.String(50), server_default="other", nullable=False),
        sa.Column("original_url", sa.String(2048), nullable=False),
        sa.Column("capture_status", sa.String(20), server_default="queued", nullable=False),
        sa.Column("capture_started_at", sa.DateTime(timezone=True)),
        sa.Column("capture_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("capture_error", sa.String(1000)),
        sa.Column("capture_timestamp", sa.DateTime(timezone=True)),
        sa.Column("hash_sha256", sa.String(64)),
        sa.Column("page_title", sa.Text()),
        sa.Column("visible_author", sa.Text()),
        sa.Column("visible_timestamp", sa.String(200)),
        sa.Column("visible_text", sa.Text()),
        sa.Column("visible_comments", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_evidence_case_id", "evidence", ["case_id"])
    op.create_table(
        "evidence_files",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("evidence_id", sa.Uuid(as_uuid=True), sa.ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("file_type", sa.String(32), nullable=False),
        sa.Column("path", sa.String(512), unique=True, nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_evidence_files_evidence_id", "evidence_files", ["evidence_id"])
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
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_table(
        "case_notes",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("case_id", sa.Uuid(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_case_notes_case_id", "case_notes", ["case_id"])
    op.execute("""
        CREATE FUNCTION reject_record_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'record is append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in ("submitted_links", "evidence_files", "ai_analyses", "audit_logs", "case_notes"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_record_mutation()")
    op.execute("""
        CREATE FUNCTION protect_captured_evidence() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' OR OLD.capture_status = 'captured' THEN
                RAISE EXCEPTION 'captured evidence is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER evidence_immutable AFTER UPDATE OR DELETE ON evidence FOR EACH ROW EXECUTE FUNCTION protect_captured_evidence()")


def downgrade() -> None:
    op.execute("DROP FUNCTION protect_captured_evidence() CASCADE")
    op.execute("DROP FUNCTION reject_record_mutation() CASCADE")
    op.drop_table("audit_logs")
    op.drop_table("case_notes")
    op.drop_table("ai_analyses")
    op.drop_table("evidence_files")
    op.drop_table("evidence")
    op.drop_column("submitted_links", "shared_text")
    op.drop_column("cases", "updated_at")
    op.drop_column("cases", "status")
    op.drop_column("cases", "victim_statement")
