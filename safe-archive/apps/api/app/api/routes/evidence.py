"""Authorized evidence metadata, file, analysis, and audit reads."""

from datetime import datetime
from hashlib import sha256
from cryptography.exceptions import InvalidTag
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_case_service, get_current_user, get_session
from app.application.cases import CaseNotFound, CaseService
from app.application.analysis import AnalysisUnavailable, analyze_visible_text
from app.core.config import get_settings
from app.domain.users import Role, User
from app.infrastructure.models import AIAnalysisRow, AuditLogRow, EvidenceFileRow, EvidenceRow
from app.infrastructure.object_storage import StorageUnavailable, storage_from_settings

router = APIRouter(tags=["evidence"])


class EvidenceResponse(BaseModel):
    id: UUID
    case_id: UUID
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

    @classmethod
    def from_row(cls, row: EvidenceRow) -> "EvidenceResponse":
        return cls.model_validate(row, from_attributes=True)


class EvidenceFileResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    file_type: str
    mime_type: str
    size: int
    hash_sha256: str
    created_at: datetime

    @classmethod
    def from_row(cls, row: EvidenceFileRow) -> "EvidenceFileResponse":
        return cls.model_validate(row, from_attributes=True)


class AnalysisResponse(BaseModel):
    id: UUID
    evidence_id: UUID
    model_name: str
    summary: str
    entities: list
    detected_threats: list
    detected_pii: list
    tags: list
    timeline: list
    created_at: datetime

    @classmethod
    def from_row(cls, row: AIAnalysisRow) -> "AnalysisResponse":
        return cls.model_validate(row, from_attributes=True)


class AuditResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    target_type: str
    target_id: UUID
    details: dict
    timestamp: datetime

    @classmethod
    def from_row(cls, row: AuditLogRow) -> "AuditResponse":
        return cls.model_validate(row, from_attributes=True)


async def accessible_evidence(
    evidence_id: UUID,
    actor: User,
    cases: CaseService,
    session: AsyncSession,
) -> EvidenceRow:
    row = await session.get(EvidenceRow, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    try:
        await cases.get_case(actor, row.case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    return row


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceResponse])
async def list_evidence(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EvidenceResponse]:
    try:
        await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    rows = await session.scalars(
        select(EvidenceRow).where(EvidenceRow.case_id == case_id).order_by(EvidenceRow.created_at, EvidenceRow.id).limit(limit).offset(offset)
    )
    return [EvidenceResponse.from_row(row) for row in rows]


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
async def read_evidence(
    evidence_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EvidenceResponse:
    return EvidenceResponse.from_row(await accessible_evidence(evidence_id, actor, cases, session))


@router.get("/evidence/{evidence_id}/files", response_model=list[EvidenceFileResponse])
async def list_files(
    evidence_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EvidenceFileResponse]:
    await accessible_evidence(evidence_id, actor, cases, session)
    rows = await session.scalars(select(EvidenceFileRow).where(EvidenceFileRow.evidence_id == evidence_id).order_by(EvidenceFileRow.created_at))
    return [EvidenceFileResponse.from_row(row) for row in rows]


@router.get("/evidence/{evidence_id}/files/{file_id}")
async def download_file(
    evidence_id: UUID,
    file_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await accessible_evidence(evidence_id, actor, cases, session)
    row = await session.get(EvidenceFileRow, file_id)
    if row is None or row.evidence_id != evidence_id:
        raise HTTPException(status_code=404, detail="Evidence file not found")
    try:
        storage = storage_from_settings(get_settings())
        payload = await run_in_threadpool(storage.read, row.path)
    except (StorageUnavailable, FileNotFoundError) as exc:
        raise HTTPException(status_code=503, detail="Evidence storage unavailable") from exc
    except InvalidTag as exc:
        raise HTTPException(status_code=500, detail="Evidence integrity check failed") from exc
    if sha256(payload).hexdigest() != row.hash_sha256:
        raise HTTPException(status_code=500, detail="Evidence integrity check failed")
    session.add(AuditLogRow(user_id=actor.id, action="evidence.file_downloaded", target_type="evidence", target_id=evidence_id, details={"file_id": str(file_id), "sha256": row.hash_sha256}))
    await session.commit()
    return Response(
        content=payload,
        media_type=row.mime_type,
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="{row.file_type}-{row.id}"'},
    )


@router.get("/evidence/{evidence_id}/analyses", response_model=list[AnalysisResponse])
async def list_analyses(
    evidence_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AnalysisResponse]:
    await accessible_evidence(evidence_id, actor, cases, session)
    rows = await session.scalars(select(AIAnalysisRow).where(AIAnalysisRow.evidence_id == evidence_id).order_by(AIAnalysisRow.created_at.desc()))
    return [AnalysisResponse.from_row(row) for row in rows]


@router.post("/evidence/{evidence_id}/analyses", response_model=AnalysisResponse, status_code=201)
async def create_analysis(
    evidence_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AnalysisResponse:
    row = await accessible_evidence(evidence_id, actor, cases, session)
    if actor.role not in {Role.NGO_INVESTIGATOR, Role.ADMINISTRATOR}:
        raise HTTPException(status_code=403, detail="Investigator access required")
    if row.capture_status != "captured" or not row.visible_text:
        raise HTTPException(status_code=409, detail="Captured visible text is not available")
    settings = get_settings()
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        raise HTTPException(status_code=503, detail="AI analysis is not configured")
    try:
        result = await analyze_visible_text(
            row.visible_text,
            api_key=settings.openai_api_key.get_secret_value(),
            model=settings.openai_model,
        )
    except AnalysisUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Analysis provider unavailable") from exc
    analysis = AIAnalysisRow(
        evidence_id=evidence_id,
        model_name=settings.openai_model,
        **result.model_dump(),
    )
    session.add(analysis)
    await session.flush()
    session.add(AuditLogRow(user_id=actor.id, action="analysis.created", target_type="evidence", target_id=evidence_id, details={"analysis_id": str(analysis.id)}))
    await session.commit()
    await session.refresh(analysis)
    return AnalysisResponse.from_row(analysis)


@router.post("/evidence/{evidence_id}/retry", response_model=EvidenceResponse)
async def retry_capture(
    evidence_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EvidenceResponse:
    row = await accessible_evidence(evidence_id, actor, cases, session)
    if actor.role == Role.VICTIM:
        raise HTTPException(status_code=403, detail="Investigator access required")
    if row.capture_status != "failed":
        raise HTTPException(status_code=409, detail="Only failed captures can be retried")
    row.capture_status = "queued"
    row.capture_error = None
    row.capture_started_at = None
    session.add(AuditLogRow(user_id=actor.id, action="evidence.capture_retried", target_type="evidence", target_id=evidence_id, details={"attempt": row.capture_attempts + 1}))
    await session.commit()
    await session.refresh(row)
    return EvidenceResponse.from_row(row)


@router.get("/cases/{case_id}/audit", response_model=list[AuditResponse])
async def list_audit(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AuditResponse]:
    try:
        await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    if actor.role == Role.VICTIM:
        raise HTTPException(status_code=403, detail="Investigator access required")
    evidence_ids = select(EvidenceRow.id).where(EvidenceRow.case_id == case_id)
    rows = await session.scalars(
        select(AuditLogRow)
        .where((AuditLogRow.target_id == case_id) | (AuditLogRow.target_id.in_(evidence_ids)))
        .order_by(AuditLogRow.timestamp, AuditLogRow.id)
        .limit(500)
    )
    return [AuditResponse.from_row(row) for row in rows]
