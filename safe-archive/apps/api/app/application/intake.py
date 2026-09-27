"""Victim report intake creates a case and queued evidence atomically."""

from dataclasses import dataclass
from uuid import UUID

from app.domain.users import Role, User


class IntakeDenied(Exception):
    pass


@dataclass(frozen=True, slots=True)
class IntakeReceipt:
    case_id: UUID
    evidence_id: UUID
    capture_status: str


class IntakeService:
    def __init__(self, repository) -> None:
        self._repository = repository

    async def submit(
        self,
        actor: User,
        *,
        url: str,
        shared_text: str | None,
        victim_statement: str | None,
    ) -> IntakeReceipt:
        if actor.role != Role.VICTIM or not actor.is_active:
            raise IntakeDenied
        return await self._repository.submit(actor.id, url, shared_text, victim_statement)
