"""Authenticated case and submitted-link endpoints."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_case_service, get_current_user, get_session, require_roles
from app.application.cases import CaseClosed, CaseNotFound, CasePermissionDenied, CaseService, InvalidInvestigator
from app.domain.cases import Case, SubmittedLink
from app.domain.users import Role, User
from app.infrastructure.case_repository import to_case
from app.infrastructure.models import AuditLogRow, CaseNoteRow, CaseRow, SubmittedLinkRow, EvidenceRow

router = APIRouter(prefix="/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title must not be blank")
        return value


class AssignInvestigatorRequest(BaseModel):
    investigator_id: UUID | None


class SubmitLinkRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if any(character.isspace() or ord(character) < 32 for character in value):
            raise ValueError("URL must not contain whitespace or control characters")
        try:
            parts = urlsplit(value)
            if parts.scheme.lower() not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
                raise ValueError("Only HTTP(S) URLs without embedded credentials are accepted")
            _ = parts.port
        except ValueError as exc:
            raise ValueError("Enter a valid HTTP(S) URL") from exc
        return value


class UpdateCaseRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    victim_statement: str | None = Field(default=None, max_length=4000)
    status: Literal["open", "in_review", "closed", "archived"] | None = None


class CaseNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class CaseNoteResponse(BaseModel):
    id: UUID
    case_id: UUID
    user_id: UUID
    body: str
    created_at: datetime


class TimelineEvent(BaseModel):
    timestamp: datetime
    kind: str
    reference_id: UUID
    description: str


class CaseResponse(BaseModel):
    id: UUID
    owner_id: UUID
    assigned_investigator_id: UUID | None
    title: str
    created_at: datetime
    victim_statement: str | None
    status: str
    updated_at: datetime | None

    @classmethod
    def from_domain(cls, case: Case) -> "CaseResponse":
        return cls(
            id=case.id,
            owner_id=case.owner_id,
            assigned_investigator_id=case.assigned_investigator_id,
            title=case.title,
            created_at=case.created_at,
            victim_statement=case.victim_statement,
            status=case.status,
            updated_at=case.updated_at,
        )


class LinkResponse(BaseModel):
    id: UUID
    case_id: UUID
    submitted_by: UUID
    url: str
    created_at: datetime
    shared_text: str | None = None
    evidence_id: UUID | None = None

    @classmethod
    def from_domain(cls, link: SubmittedLink) -> "LinkResponse":
        return cls(id=link.id, case_id=link.case_id, submitted_by=link.submitted_by, url=link.url, created_at=link.created_at, shared_text=link.shared_text, evidence_id=link.evidence_id)


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CreateCaseRequest,
    actor: Annotated[User, Depends(require_roles(Role.VICTIM))],
    cases: Annotated[CaseService, Depends(get_case_service)],
) -> CaseResponse:
    try:
        return CaseResponse.from_domain(await cases.create_case(actor, payload.title))
    except CasePermissionDenied as exc:
        raise HTTPException(status_code=403, detail="Insufficient permissions") from exc


@router.get("", response_model=list[CaseResponse])
async def list_cases(
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> list[CaseResponse]:
    try:
        if q and q.strip():
            found = await cases.search_cases(actor, q.strip(), limit, offset)
        else:
            found = await cases.list_cases(actor, limit, offset)
        return [CaseResponse.from_domain(case) for case in found]
    except CasePermissionDenied as exc:
        raise HTTPException(status_code=403, detail="Insufficient permissions") from exc


@router.get("/stats", response_model=dict[str, int])
async def case_stats(
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int]:
    query = select(CaseRow.status, func.count(CaseRow.id)).group_by(CaseRow.status)
    if actor.role == Role.VICTIM:
        query = query.where(CaseRow.owner_id == actor.id)
    elif actor.role == Role.NGO_INVESTIGATOR:
        query = query.where(CaseRow.assigned_investigator_id == actor.id)
    counts = {status: count for status, count in await session.execute(query)}
    return {"total": sum(counts.values()), "open": counts.get("open", 0), "in_review": counts.get("in_review", 0), "closed": counts.get("closed", 0), "archived": counts.get("archived", 0)}


@router.get("/{case_id}", response_model=CaseResponse)
async def read_case(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
) -> CaseResponse:
    try:
        return CaseResponse.from_domain(await cases.get_case(actor, case_id))
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.patch("/{case_id}/assignment", response_model=CaseResponse)
async def assign_investigator(
    case_id: UUID,
    payload: AssignInvestigatorRequest,
    actor: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseResponse:
    session.add(AuditLogRow(user_id=actor.id, action="case.assigned", target_type="case", target_id=case_id, details={"investigator_id": str(payload.investigator_id) if payload.investigator_id else None}))
    try:
        case = await cases.assign_investigator(actor, case_id, payload.investigator_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except InvalidInvestigator as exc:
        raise HTTPException(status_code=422, detail="Investigator must be an active NGO investigator account") from exc
    except CasePermissionDenied as exc:
        raise HTTPException(status_code=403, detail="Insufficient permissions") from exc
    return CaseResponse.from_domain(case)


@router.post("/{case_id}/links", response_model=LinkResponse, status_code=status.HTTP_201_CREATED)
async def submit_link(
    case_id: UUID,
    payload: SubmitLinkRequest,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
) -> LinkResponse:
    try:
        return LinkResponse.from_domain(await cases.add_link(actor, case_id, payload.url))
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except CaseClosed as exc:
        raise HTTPException(status_code=409, detail="Closed cases cannot accept new links") from exc


@router.get("/{case_id}/links", response_model=list[LinkResponse])
async def list_links(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LinkResponse]:
    try:
        return [LinkResponse.from_domain(link) for link in await cases.list_links(actor, case_id, limit, offset)]
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: UUID,
    payload: UpdateCaseRequest,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseResponse:
    try:
        case = await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    if case.status == "archived":
        raise HTTPException(status_code=409, detail="Archived cases cannot be changed")
    requested = payload.model_fields_set
    if actor.role == Role.VICTIM:
        if case.status != "open" or "status" in requested:
            raise HTTPException(status_code=403, detail="Case is not editable by its owner")
    elif "victim_statement" in requested:
        raise HTTPException(status_code=403, detail="Only the owner can edit the victim statement")
    row = await session.get(CaseRow, case_id)
    assert row is not None
    if "title" in requested:
        if not payload.title or not payload.title.strip():
            raise HTTPException(status_code=422, detail="Title must not be blank")
        row.title = payload.title.strip()
    if "victim_statement" in requested:
        row.victim_statement = payload.victim_statement
    if "status" in requested:
        if payload.status is None:
            raise HTTPException(status_code=422, detail="Status cannot be null")
        row.status = payload.status
    row.updated_at = datetime.now(timezone.utc)
    session.add(AuditLogRow(user_id=actor.id, action="case.updated", target_type="case", target_id=case_id, details={"fields": sorted(requested)}))
    await session.commit()
    await session.refresh(row)
    return CaseResponse.from_domain(to_case(row))


@router.delete("/{case_id}", status_code=204)
async def archive_case(
    case_id: UUID,
    actor: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    try:
        await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    row = await session.get(CaseRow, case_id)
    assert row is not None
    row.status = "archived"
    row.updated_at = datetime.now(timezone.utc)
    session.add(AuditLogRow(user_id=actor.id, action="case.archived", target_type="case", target_id=case_id, details={}))
    await session.commit()


@router.post("/{case_id}/notes", response_model=CaseNoteResponse, status_code=201)
async def add_note(
    case_id: UUID,
    payload: CaseNoteRequest,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CaseNoteResponse:
    try:
        await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    if actor.role == Role.VICTIM:
        raise HTTPException(status_code=403, detail="Investigator access required")
    note = CaseNoteRow(case_id=case_id, user_id=actor.id, body=payload.body.strip())
    if not note.body:
        raise HTTPException(status_code=422, detail="Note must not be blank")
    session.add(note)
    await session.flush()
    session.add(AuditLogRow(user_id=actor.id, action="case.note_added", target_type="case", target_id=case_id, details={"note_id": str(note.id)}))
    await session.commit()
    await session.refresh(note)
    return CaseNoteResponse.model_validate(note, from_attributes=True)


@router.get("/{case_id}/notes", response_model=list[CaseNoteResponse])
async def list_notes(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[CaseNoteResponse]:
    try:
        await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    if actor.role == Role.VICTIM:
        raise HTTPException(status_code=403, detail="Investigator access required")
    rows = await session.scalars(select(CaseNoteRow).where(CaseNoteRow.case_id == case_id).order_by(CaseNoteRow.created_at, CaseNoteRow.id).limit(500))
    return [CaseNoteResponse.model_validate(row, from_attributes=True) for row in rows]


@router.get("/{case_id}/timeline", response_model=list[TimelineEvent])
async def case_timeline(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TimelineEvent]:
    try:
        case = await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    events = [TimelineEvent(timestamp=case.created_at, kind="case", reference_id=case.id, description="Case created")]
    links = await session.scalars(select(SubmittedLinkRow).where(SubmittedLinkRow.case_id == case_id))
    for link in links:
        events.append(TimelineEvent(timestamp=link.created_at, kind="submission", reference_id=link.id, description="Public link submitted"))
    evidence_rows = list(await session.scalars(select(EvidenceRow).where(EvidenceRow.case_id == case_id)))
    for evidence in evidence_rows:
        if evidence.capture_timestamp:
            events.append(TimelineEvent(timestamp=evidence.capture_timestamp, kind="capture", reference_id=evidence.id, description="Public page captured"))
    return sorted(events, key=lambda event: (event.timestamp, str(event.reference_id)))
