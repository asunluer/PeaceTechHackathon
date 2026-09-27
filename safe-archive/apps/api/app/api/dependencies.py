"""Request-scoped authentication dependencies and role guards."""

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth import AuthService, InvalidAccessToken
from app.application.cases import CaseService
from app.application.intake import IntakeService
from app.core.config import get_settings
from app.domain.users import Role, User
from app.infrastructure.security import PyJwtTokenCodec, get_password_hasher
from app.infrastructure.case_repository import SqlAlchemyCaseRepository
from app.infrastructure.intake_repository import SqlAlchemyIntakeRepository
from app.infrastructure.user_repository import SqlAlchemyUserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.database.sessions() as session:
        yield session


def get_auth_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AuthService:
    return AuthService(
        users=SqlAlchemyUserRepository(session),
        passwords=get_password_hasher(),
        tokens=PyJwtTokenCodec(get_settings()),
    )


def get_case_service(session: Annotated[AsyncSession, Depends(get_session)]) -> CaseService:
    return CaseService(
        cases=SqlAlchemyCaseRepository(session),
        users=SqlAlchemyUserRepository(session),
    )


def get_intake_service(session: Annotated[AsyncSession, Depends(get_session)]) -> IntakeService:
    return IntakeService(SqlAlchemyIntakeRepository(session))


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    try:
        return await auth.current_user(token)
    except InvalidAccessToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles(*allowed: Role) -> Callable[..., Coroutine[Any, Any, User]]:
    async def authorize(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return authorize
