"""Atomic PostgreSQL report submission."""

from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.intake import IntakeReceipt
from app.infrastructure.models import AuditLogRow, CaseRow, EvidenceRow, SubmittedLinkRow


def platform_for(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    platforms = {
        "instagram.com": "instagram",
        "facebook.com": "facebook",
        "fb.com": "facebook",
        "tiktok.com": "tiktok",
        "threads.net": "threads",
        "x.com": "x",
        "twitter.com": "x",
    }
    for domain, name in platforms.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "other"


class SqlAlchemyIntakeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def submit(
        self,
        owner_id: UUID,
        url: str,
        shared_text: str | None,
        victim_statement: str | None,
    ) -> IntakeReceipt:
        platform = platform_for(url)
        case = CaseRow(
            owner_id=owner_id,
            title=f"Report from {platform.title() if platform != 'x' else 'X'}",
            victim_statement=victim_statement,
        )
        self._session.add(case)
        await self._session.flush()
        link = SubmittedLinkRow(case_id=case.id, submitted_by=owner_id, url=url, shared_text=shared_text)
        self._session.add(link)
        await self._session.flush()
        evidence = EvidenceRow(
            case_id=case.id,
            submitted_link_id=link.id,
            platform=platform,
            original_url=url,
            capture_status="queued",
        )
        self._session.add(evidence)
        await self._session.flush()
        self._session.add(
            AuditLogRow(
                user_id=owner_id,
                action="report.submitted",
                target_type="evidence",
                target_id=evidence.id,
                details={"case_id": str(case.id)},
            )
        )
        await self._session.commit()
        return IntakeReceipt(case.id, evidence.id, evidence.capture_status)
