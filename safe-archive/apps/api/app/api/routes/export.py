"""Authorized PDF report export."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_case_service, get_current_user, get_session
from app.application.cases import CaseNotFound, CaseService
from app.application.reporting import build_case_report
from app.domain.users import Role, User
from app.infrastructure.models import AIAnalysisRow, AuditLogRow, EvidenceFileRow, EvidenceRow

router = APIRouter(tags=["reports"])


@router.get("/cases/{case_id}/report.pdf")
async def export_case_report(
    case_id: UUID,
    actor: Annotated[User, Depends(get_current_user)],
    cases: Annotated[CaseService, Depends(get_case_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    try:
        case = await cases.get_case(actor, case_id)
    except CaseNotFound as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    if actor.role == Role.VICTIM:
        raise HTTPException(status_code=403, detail="Investigator access required")
    evidence = list(await session.scalars(select(EvidenceRow).where(EvidenceRow.case_id == case_id).order_by(EvidenceRow.created_at)))
    files_by_evidence = {}
    analyses_by_evidence = {}
    for row in evidence:
        files_by_evidence[row.id] = list(await session.scalars(select(EvidenceFileRow).where(EvidenceFileRow.evidence_id == row.id)))
        analyses_by_evidence[row.id] = list(await session.scalars(select(AIAnalysisRow).where(AIAnalysisRow.evidence_id == row.id).order_by(AIAnalysisRow.created_at)))
    payload = await run_in_threadpool(build_case_report, case, evidence, files_by_evidence, analyses_by_evidence)
    session.add(AuditLogRow(user_id=actor.id, action="report.exported", target_type="case", target_id=case_id, details={"evidence_count": len(evidence)}))
    await session.commit()
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={"Cache-Control": "no-store", "Content-Disposition": f'attachment; filename="safe-archive-{case_id}.pdf"'},
    )
