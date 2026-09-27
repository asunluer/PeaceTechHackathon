"""Token issue, current account, and token revocation endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_auth_service, get_current_user
from app.application.auth import AuthService, InvalidCredentials
from app.domain.users import Role, User

router = APIRouter(prefix="/auth", tags=["authentication"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    role: Role
    is_active: bool
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


@router.post("/token", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth: Annotated[AuthService, Depends(get_auth_service)],
    response: Response,
) -> TokenResponse:
    try:
        token = await auth.authenticate(form.username, form.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=token.value, expires_in=token.expires_in)


@router.get("/me", response_model=UserResponse)
async def read_current_user(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: Annotated[User, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    await auth.revoke_tokens(user.id)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    try:
        await auth.change_password(user, payload.current_password, payload.new_password)
    except InvalidCredentials as exc:
        raise HTTPException(status_code=400, detail="Current password is incorrect") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
