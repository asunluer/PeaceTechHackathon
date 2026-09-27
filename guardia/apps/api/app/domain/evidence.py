"""Evidence identity and capture state."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Evidence:
    id: UUID
    case_id: UUID
    submitted_link_id: UUID
    platform: str
    original_url: str
    capture_status: str
    capture_error: str | None
    capture_timestamp: datetime | None
    hash_sha256: str | None
    page_title: str | None
    visible_author: str | None
    visible_timestamp: str | None
    visible_text: str | None
    visible_comments: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EvidenceFile:
    id: UUID
    evidence_id: UUID
    file_type: str
    path: str
    mime_type: str
    size: int
    hash_sha256: str
    created_at: datetime
