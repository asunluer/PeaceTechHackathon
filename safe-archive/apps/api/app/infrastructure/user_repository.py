"""SQLAlchemy implementation of user persistence."""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import DuplicateEmail
from app.domain.users import Role, User
from app.infrastructure.models import UserRow


def to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        role=row.role,
        is_active=row.is_active,
        token_version=row.token_version,
        created_at=row.created_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserRow).where(UserRow.email == email))
        return to_domain(row) if row else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return to_domain(row) if row else None

    async def has_administrator(self) -> bool:
        user_id = await self._session.scalar(
            select(UserRow.id).where(UserRow.role == Role.ADMINISTRATOR).limit(1)
        )
        return user_id is not None

    async def create(self, email: str, password_hash: str, role: Role) -> User:
        row = UserRow(email=email, password_hash=password_hash, role=role)
        self._session.add(row)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateEmail from exc
        await self._session.refresh(row)
        return to_domain(row)

    async def revoke_tokens(self, user_id: UUID) -> None:
        await self._session.execute(
            update(UserRow)
            .where(UserRow.id == user_id)
            .values(token_version=UserRow.token_version + 1)
        )
        await self._session.commit()
