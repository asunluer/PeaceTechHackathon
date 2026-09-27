"""Case records and submitted links, before any public-page capture occurs."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Case:
    id: UUID
    owner_id: UUID
    assigned_investigator_id: UUID | None
    title: str
    created_at: datetime
    victim_statement: str | None = None
    status: str = "open"
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SubmittedLink:
    id: UUID
    case_id: UUID
    submitted_by: UUID
    url: str
    created_at: datetime
    shared_text: str | None = None
    evidence_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    id: UUID
    submitted_link_id: UUID
    kind: str
    source_url: str
    media_type: str
    captured_by: str
    captured_at: datetime
    stored_at: datetime
    sha256: str
    payload: bytes
