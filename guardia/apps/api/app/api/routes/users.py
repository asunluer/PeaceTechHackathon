"""Administrator-controlled account provisioning."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_auth_service, get_session, require_roles
from app.api.routes.auth import UserResponse
from app.application.auth import AuthService, DuplicateEmail
from app.domain.users import Role, User
from app.infrastructure.models import AuditLogRow, UserRow

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Role


class UpdateUserRequest(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    administrator: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    try:
        user = await auth.create_user(administrator, str(payload.email), payload.password, payload.role)
    except DuplicateEmail as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists") from exc
    return UserResponse.model_validate(user)


@router.get("", response_model=list[UserResponse])
async def list_users(
    administrator: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    role: Role | None = None,
    active: bool | None = None,
) -> list[UserResponse]:
    query = select(UserRow)
    if role is not None:
        query = query.where(UserRow.role == role)
    if active is not None:
        query = query.where(UserRow.is_active.is_(active))
    rows = await session.scalars(query.order_by(UserRow.created_at.desc(), UserRow.id.desc()).limit(limit).offset(offset))
    return [UserResponse.model_validate(row) for row in rows]


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UpdateUserRequest,
    administrator: Annotated[User, Depends(require_roles(Role.ADMINISTRATOR))],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserResponse:
    row = await session.get(UserRow, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    next_role = payload.role if payload.role is not None else row.role
    next_active = payload.is_active if payload.is_active is not None else row.is_active
    if row.role == Role.ADMINISTRATOR and row.is_active and (next_role != Role.ADMINISTRATOR or not next_active):
        await session.execute(select(func.pg_advisory_xact_lock(87410923)))
        active_admins = await session.scalar(select(func.count(UserRow.id)).where(UserRow.role == Role.ADMINISTRATOR, UserRow.is_active.is_(True)))
        if active_admins is None or active_admins <= 1:
            raise HTTPException(status_code=409, detail="The last active administrator cannot be removed")
    if row.role != next_role or row.is_active != next_active:
        row.role = next_role
        row.is_active = next_active
        row.token_version += 1
        session.add(AuditLogRow(user_id=administrator.id, action="user.updated", target_type="user", target_id=user_id, details={"role": next_role.value, "is_active": next_active}))
        await session.commit()
        await session.refresh(row)
    return UserResponse.model_validate(row)
