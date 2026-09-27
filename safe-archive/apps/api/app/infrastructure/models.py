"""SQLAlchemy mapping for durable user accounts."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, JSON, LargeBinary, String, Text, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.users import Role


class Base(DeclarativeBase):
    pass


role_type = Enum(
    Role,
    name="user_role",
    native_enum=False,
    create_constraint=True,
    values_callable=lambda enum: [role.value for role in enum],
)


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("token_version >= 0", name="ck_users_token_version"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[Role] = mapped_column(role_type, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CaseRow(Base):
    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_investigator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    victim_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SubmittedLinkRow(Base):
    __tablename__ = "submitted_links"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    submitted_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    shared_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvidenceArtifactRow(Base):
    __tablename__ = "evidence_artifacts"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0 AND size_bytes <= 26214400", name="ck_evidence_artifacts_size"),
        CheckConstraint("size_bytes = octet_length(payload)", name="ck_evidence_artifacts_payload_size"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    submitted_link_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submitted_links.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    captured_by: Mapped[str] = mapped_column(String(100), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    submitted_link_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("submitted_links.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, server_default="other")
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    capture_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    capture_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    capture_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    capture_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    visible_author: Mapped[str | None] = mapped_column(Text, nullable=True)
    visible_timestamp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    visible_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visible_comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvidenceFileRow(Base):
    __tablename__ = "evidence_files"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False)
    path: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AIAnalysisRow(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    evidence_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT"), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    entities: Mapped[list] = mapped_column(JSON, nullable=False)
    detected_threats: Mapped[list] = mapped_column(JSON, nullable=False)
    detected_pii: Mapped[list] = mapped_column(JSON, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False)
    timeline: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CaseNoteRow(Base):
    __tablename__ = "case_notes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
