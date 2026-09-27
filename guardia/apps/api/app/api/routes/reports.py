"""Mobile report submission endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, get_intake_service
from app.api.routes.cases import SubmitLinkRequest
from app.application.intake import IntakeDenied, IntakeService
from app.domain.users import User

router = APIRouter(prefix="/reports", tags=["reports"])


class SubmitReportRequest(SubmitLinkRequest):
    shared_text: str | None = Field(default=None, max_length=4000)
    victim_statement: str | None = Field(default=None, max_length=4000)


class SubmitReportResponse(BaseModel):
    case_id: UUID
    evidence_id: UUID
    capture_status: str


@router.post("", response_model=SubmitReportResponse, status_code=status.HTTP_201_CREATED)
async def submit_report(
    payload: SubmitReportRequest,
    actor: Annotated[User, Depends(get_current_user)],
    intake: Annotated[IntakeService, Depends(get_intake_service)],
) -> SubmitReportResponse:
    try:
        receipt = await intake.submit(
            actor,
            url=payload.url,
            shared_text=payload.shared_text,
            victim_statement=payload.victim_statement,
        )
    except IntakeDenied as exc:
        raise HTTPException(status_code=403, detail="Only victim accounts can submit reports") from exc
    return SubmitReportResponse(
        case_id=receipt.case_id,
        evidence_id=receipt.evidence_id,
        capture_status=receipt.capture_status,
    )
