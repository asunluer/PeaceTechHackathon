"""Persist cases and submitted public links.

Revision ID: 20260926_02
Revises: 20260926_01
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "20260926_02"
down_revision = "20260926_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column(
            "assigned_investigator_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_cases_owner_id", "cases", ["owner_id"])
    op.create_index("ix_cases_assigned_investigator_id", "cases", ["assigned_investigator_id"])

    op.create_table(
        "submitted_links",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("case_id", sa.Uuid(as_uuid=True), sa.ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("submitted_by", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_submitted_links_case_id", "submitted_links", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_submitted_links_case_id", table_name="submitted_links")
    op.drop_table("submitted_links")
    op.drop_index("ix_cases_assigned_investigator_id", table_name="cases")
    op.drop_index("ix_cases_owner_id", table_name="cases")
    op.drop_table("cases")
