"""Security-focused authentication use case tests."""

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from pydantic import SecretStr

from app.application.auth import (
    AuthService,
    DuplicateEmail,
    InvalidAccessToken,
    InvalidCredentials,
    PermissionDenied,
)
from app.core.config import Settings
from app.domain.users import Role, User
from app.infrastructure.security import AUDIENCE, ISSUER, Argon2PasswordHasher, PyJwtTokenCodec


class MemoryUsers:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def has_administrator(self) -> bool:
        return any(user.role == Role.ADMINISTRATOR for user in self.users.values())

    async def create(self, email: str, password_hash: str, role: Role) -> User:
        if await self.get_by_email(email):
            raise DuplicateEmail
        user = User(uuid4(), email, password_hash, role, True, 0, datetime.now(timezone.utc))
        self.users[user.id] = user
        return user

    async def revoke_tokens(self, user_id: UUID) -> None:
        self.users[user_id] = replace(self.users[user_id], token_version=self.users[user_id].token_version + 1)


@pytest.fixture
def auth() -> tuple[AuthService, MemoryUsers, Settings]:
    settings = Settings(
        db_host="localhost",
        db_name="test",
        db_user="test",
        db_password=SecretStr("test-password"),
        jwt_secret=SecretStr("a-dedicated-test-secret-with-more-than-32-bytes"),
    )
    users = MemoryUsers()
    service = AuthService(users, Argon2PasswordHasher(), PyJwtTokenCodec(settings))
    return service, users, settings


@pytest.mark.asyncio
async def test_login_and_logout_revoke_existing_token(auth: tuple[AuthService, MemoryUsers, Settings]) -> None:
    service, _, _ = auth
    user = await service.create_first_administrator(" Admin@Example.org ", "a-long-test-password")
    assert user.email == "admin@example.org"

    with pytest.raises(InvalidCredentials):
        await service.authenticate(user.email, "incorrect-password")
    with pytest.raises(InvalidCredentials):
        await service.authenticate("missing@example.org", "incorrect-password")

    token = await service.authenticate(user.email, "a-long-test-password")
    assert (await service.current_user(token.value)).id == user.id
    await service.revoke_tokens(user.id)
    with pytest.raises(InvalidAccessToken):
        await service.current_user(token.value)


@pytest.mark.asyncio
async def test_role_is_read_from_current_account(auth: tuple[AuthService, MemoryUsers, Settings]) -> None:
    service, users, _ = auth
    administrator = await service.create_first_administrator("admin@example.org", "a-long-test-password")
    investigator = await service.create_user(
        administrator, "investigator@example.org", "another-long-password", Role.NGO_INVESTIGATOR
    )
    token = await service.authenticate(investigator.email, "another-long-password")
    users.users[investigator.id] = replace(investigator, role=Role.VICTIM)
    assert (await service.current_user(token.value)).role == Role.VICTIM
    with pytest.raises(PermissionDenied):
        await service.create_user(investigator, "new@example.org", "a-long-test-password", Role.ADMINISTRATOR)


def test_rejects_tampered_and_wrong_audience_tokens(auth: tuple[AuthService, MemoryUsers, Settings]) -> None:
    _, _, settings = auth
    codec = PyJwtTokenCodec(settings)
    user = User(uuid4(), "admin@example.org", "hash", Role.ADMINISTRATOR, True, 0, datetime.now(timezone.utc))
    token = codec.issue(user).value
    with pytest.raises(InvalidAccessToken):
        codec.decode(token + "tampered")

    claims = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=AUDIENCE,
        issuer=ISSUER,
    )
    claims["aud"] = "another-service"
    wrong_audience = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm="HS256")
    with pytest.raises(InvalidAccessToken):
        codec.decode(wrong_audience)
