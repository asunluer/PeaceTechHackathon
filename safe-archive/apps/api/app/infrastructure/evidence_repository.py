"""Append-only storage for bytes captured from public pages by a future worker."""

from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cases import EvidenceArtifact
from app.infrastructure.models import EvidenceArtifactRow

MAX_ARTIFACT_BYTES = 25 * 1024 * 1024


def to_domain(row: EvidenceArtifactRow) -> EvidenceArtifact:
    return EvidenceArtifact(
        id=row.id,
        submitted_link_id=row.submitted_link_id,
        kind=row.kind,
        source_url=row.source_url,
        media_type=row.media_type,
        captured_by=row.captured_by,
        captured_at=row.captured_at,
        stored_at=row.stored_at,
        sha256=row.sha256,
        payload=row.payload,
    )


class SqlAlchemyEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store(
        self,
        submitted_link_id: UUID,
        *,
        kind: str,
        source_url: str,
        media_type: str,
        captured_by: str,
        captured_at: datetime,
        payload: bytes,
    ) -> EvidenceArtifact:
        if len(payload) > MAX_ARTIFACT_BYTES:
            raise ValueError("Artifact exceeds 25 MiB")
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError("captured_at must include a timezone")
        if not kind or len(kind) > 32 or not source_url or len(source_url) > 2048:
            raise ValueError("Invalid artifact kind or source URL")
        if not media_type or len(media_type) > 100 or not captured_by or len(captured_by) > 100:
            raise ValueError("Invalid artifact media type or capture agent")
        row = EvidenceArtifactRow(
            submitted_link_id=submitted_link_id,
            kind=kind,
            source_url=source_url,
            media_type=media_type,
            captured_by=captured_by,
            captured_at=captured_at,
            sha256=sha256(payload).hexdigest(),
            size_bytes=len(payload),
            payload=payload,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return to_domain(row)

    async def get(self, artifact_id: UUID) -> EvidenceArtifact | None:
        row = await self._session.get(EvidenceArtifactRow, artifact_id)
        return to_domain(row) if row else None
