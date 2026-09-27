"""Case access rules and append-only submitted-link use cases."""

from uuid import UUID

from app.application.ports import CaseRepository, UserRepository
from app.domain.cases import Case, SubmittedLink
from app.domain.users import Role, User


class CaseNotFound(Exception):
    pass


class CasePermissionDenied(Exception):
    pass


class InvalidInvestigator(Exception):
    pass


class CaseClosed(Exception):
    pass


class CaseService:
    def __init__(self, cases: CaseRepository, users: UserRepository) -> None:
        self._cases = cases
        self._users = users

    async def create_case(self, actor: User, title: str) -> Case:
        if actor.role != Role.VICTIM or not actor.is_active:
            raise CasePermissionDenied
        return await self._cases.create_case(actor.id, title)

    async def list_cases(self, actor: User, limit: int, offset: int) -> list[Case]:
        if not actor.is_active:
            raise CasePermissionDenied
        return await self._cases.list_cases(actor, limit, offset)

    async def search_cases(self, actor: User, query: str, limit: int, offset: int) -> list[Case]:
        if not actor.is_active:
            raise CasePermissionDenied
        return await self._cases.search_cases(actor, query, limit, offset)

    async def get_case(self, actor: User, case_id: UUID) -> Case:
        case = await self._cases.get_case(case_id)
        if case is None or not self._can_access(actor, case):
            raise CaseNotFound
        return case

    async def assign_investigator(self, actor: User, case_id: UUID, investigator_id: UUID | None) -> Case:
        if actor.role != Role.ADMINISTRATOR or not actor.is_active:
            raise CasePermissionDenied
        case = await self._cases.get_case(case_id)
        if case is None:
            raise CaseNotFound
        if investigator_id is not None:
            investigator = await self._users.get_by_id(investigator_id)
            if investigator is None or not investigator.is_active or investigator.role != Role.NGO_INVESTIGATOR:
                raise InvalidInvestigator
        return await self._cases.assign_investigator(case_id, investigator_id)

    async def add_link(self, actor: User, case_id: UUID, url: str) -> SubmittedLink:
        case = await self.get_case(actor, case_id)
        if case.status in {"closed", "archived"}:
            raise CaseClosed
        return await self._cases.add_link(case_id, actor.id, url)

    async def list_links(self, actor: User, case_id: UUID, limit: int, offset: int) -> list[SubmittedLink]:
        await self.get_case(actor, case_id)
        return await self._cases.list_links(case_id, limit, offset)

    @staticmethod
    def _can_access(actor: User, case: Case) -> bool:
        if not actor.is_active:
            return False
        return (
            actor.role == Role.ADMINISTRATOR
            or actor.role == Role.VICTIM and case.owner_id == actor.id
            or actor.role == Role.NGO_INVESTIGATOR and case.assigned_investigator_id == actor.id
        )
