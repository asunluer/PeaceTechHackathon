"""Ports used by the authentication use cases."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.cases import Case, SubmittedLink
from app.domain.users import Role, User


@dataclass(frozen=True, slots=True)
class AccessToken:
    value: str
    expires_in: int


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    user_id: UUID
    token_version: int


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def has_administrator(self) -> bool: ...

    async def create(self, email: str, password_hash: str, role: Role) -> User: ...

    async def revoke_tokens(self, user_id: UUID) -> None: ...


class PasswordHasher(Protocol):
    async def hash(self, password: str) -> str: ...

    async def verify(self, password: str, password_hash: str | None) -> bool: ...


class TokenCodec(Protocol):
    def issue(self, user: User) -> AccessToken: ...

    def decode(self, value: str) -> TokenIdentity: ...


class CaseRepository(Protocol):
    async def create_case(self, owner_id: UUID, title: str) -> Case: ...

    async def get_case(self, case_id: UUID) -> Case | None: ...

    async def list_cases(self, actor: User, limit: int, offset: int) -> list[Case]: ...

    async def search_cases(self, actor: User, query: str, limit: int, offset: int) -> list[Case]: ...

    async def assign_investigator(self, case_id: UUID, investigator_id: UUID | None) -> Case: ...

    async def add_link(self, case_id: UUID, submitted_by: UUID, url: str) -> SubmittedLink: ...

    async def list_links(self, case_id: UUID, limit: int, offset: int) -> list[SubmittedLink]: ...
