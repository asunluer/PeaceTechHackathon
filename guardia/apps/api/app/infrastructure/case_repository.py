"""PostgreSQL persistence for cases and submitted links."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cases import Case, SubmittedLink
from app.domain.users import Role, User
from app.infrastructure.models import AuditLogRow, CaseRow, EvidenceRow, SubmittedLinkRow
from app.infrastructure.intake_repository import platform_for


def to_case(row: CaseRow) -> Case:
    return Case(row.id, row.owner_id, row.assigned_investigator_id, row.title, row.created_at, row.victim_statement, row.status, row.updated_at)


def to_link(row: SubmittedLinkRow) -> SubmittedLink:
    return SubmittedLink(row.id, row.case_id, row.submitted_by, row.url, row.created_at, row.shared_text)


class SqlAlchemyCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_case(self, owner_id: UUID, title: str) -> Case:
        row = CaseRow(owner_id=owner_id, title=title)
        self._session.add(row)
        await self._session.flush()
        self._session.add(AuditLogRow(user_id=owner_id, action="case.created", target_type="case", target_id=row.id, details={}))
        await self._session.commit()
        await self._session.refresh(row)
        return to_case(row)

    async def get_case(self, case_id: UUID) -> Case | None:
        row = await self._session.get(CaseRow, case_id)
        return to_case(row) if row else None

    @staticmethod
    def _scoped_to_actor(query, actor: User):
        if actor.role == Role.VICTIM:
            return query.where(CaseRow.owner_id == actor.id)
        if actor.role == Role.NGO_INVESTIGATOR:
            return query.where(CaseRow.assigned_investigator_id == actor.id)
        if actor.role == Role.ADMINISTRATOR:
            return query
        return None

    async def list_cases(self, actor: User, limit: int, offset: int) -> list[Case]:
        query = self._scoped_to_actor(select(CaseRow), actor)
        if query is None:
            return []
        query = query.order_by(CaseRow.created_at.desc(), CaseRow.id.desc()).limit(limit).offset(offset)
        rows = await self._session.scalars(query)
        return [to_case(row) for row in rows]

    async def search_cases(self, actor: User, query_text: str, limit: int, offset: int) -> list[Case]:
        base = self._scoped_to_actor(select(CaseRow), actor)
        if base is None:
            return []
        escaped = query_text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = (
            base.outerjoin(SubmittedLinkRow, SubmittedLinkRow.case_id == CaseRow.id)
            .outerjoin(EvidenceRow, EvidenceRow.submitted_link_id == SubmittedLinkRow.id)
        )
        predicates = [
            CaseRow.title.ilike(pattern, escape="\\"),
            CaseRow.victim_statement.ilike(pattern, escape="\\"),
            EvidenceRow.page_title.ilike(pattern, escape="\\"),
            EvidenceRow.visible_text.ilike(pattern, escape="\\"),
            EvidenceRow.original_url.ilike(pattern, escape="\\"),
        ]
        query = (
            query.where(or_(*predicates))
            .distinct()
            .order_by(CaseRow.created_at.desc(), CaseRow.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.scalars(query)
        return [to_case(row) for row in rows]

    async def assign_investigator(self, case_id: UUID, investigator_id: UUID | None) -> Case:
        row = await self._session.get(CaseRow, case_id)
        assert row is not None
        row.assigned_investigator_id = investigator_id
        await self._session.commit()
        await self._session.refresh(row)
        return to_case(row)

    async def add_link(self, case_id: UUID, submitted_by: UUID, url: str) -> SubmittedLink:
        row = SubmittedLinkRow(case_id=case_id, submitted_by=submitted_by, url=url)
        self._session.add(row)
        await self._session.flush()
        evidence = EvidenceRow(
            case_id=case_id,
            submitted_link_id=row.id,
            platform=platform_for(url),
            original_url=url,
            capture_status="queued",
        )
        self._session.add(evidence)
        await self._session.flush()
        self._session.add(AuditLogRow(user_id=submitted_by, action="link.submitted", target_type="evidence", target_id=evidence.id, details={"case_id": str(case_id)}))
        await self._session.commit()
        await self._session.refresh(row)
        link = to_link(row)
        return SubmittedLink(link.id, link.case_id, link.submitted_by, link.url, link.created_at, link.shared_text, evidence.id)

    async def list_links(self, case_id: UUID, limit: int, offset: int) -> list[SubmittedLink]:
        query = (
            select(SubmittedLinkRow, EvidenceRow.id)
            .outerjoin(EvidenceRow, EvidenceRow.submitted_link_id == SubmittedLinkRow.id)
            .where(SubmittedLinkRow.case_id == case_id)
            .order_by(SubmittedLinkRow.created_at.asc(), SubmittedLinkRow.id.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = await self._session.execute(query)
        return [
            SubmittedLink(row.id, row.case_id, row.submitted_by, row.url, row.created_at, row.shared_text, evidence_id)
            for row, evidence_id in rows
        ]
