"""Authentication and account provisioning use cases."""

from uuid import UUID

from app.application.ports import AccessToken, PasswordHasher, TokenCodec, UserRepository
from app.domain.users import Role, User


class InvalidCredentials(Exception):
    pass


class InvalidAccessToken(Exception):
    pass


class DuplicateEmail(Exception):
    pass


class PermissionDenied(Exception):
    pass


class AdministratorExists(Exception):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordHasher,
        tokens: TokenCodec,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._tokens = tokens

    async def authenticate(self, email: str, password: str) -> AccessToken:
        user = await self._users.get_by_email(normalize_email(email))
        password_hash = user.password_hash if user is not None and user.is_active else None
        password_valid = await self._passwords.verify(password, password_hash)
        if user is None or not user.is_active or not password_valid:
            raise InvalidCredentials
        return self._tokens.issue(user)

    async def current_user(self, token: str) -> User:
        identity = self._tokens.decode(token)
        user = await self._users.get_by_id(identity.user_id)
        if user is None or not user.is_active or user.token_version != identity.token_version:
            raise InvalidAccessToken
        return user

    async def create_user(self, actor: User, email: str, password: str, role: Role) -> User:
        if actor.role != Role.ADMINISTRATOR or not actor.is_active:
            raise PermissionDenied
        return await self._create_user(email, password, role, created_by=actor.id)

    async def create_first_administrator(self, email: str, password: str) -> User:
        if await self._users.has_administrator():
            raise AdministratorExists
        return await self._create_user(email, password, Role.ADMINISTRATOR)

    async def revoke_tokens(self, user_id: UUID) -> None:
        await self._users.revoke_tokens(user_id)

    async def change_password(self, actor: User, current_password: str, new_password: str) -> None:
        if not await self._passwords.verify(current_password, actor.password_hash):
            raise InvalidCredentials
        if not 12 <= len(new_password) <= 128 or new_password == current_password:
            raise ValueError("New password must be different and contain 12 to 128 characters")
        await self._users.change_password(actor.id, await self._passwords.hash(new_password))

    async def _create_user(self, email: str, password: str, role: Role, created_by: UUID | None = None) -> User:
        if len(password) < 12 or len(password) > 128:
            raise ValueError("Password must contain between 12 and 128 characters")
        password_hash = await self._passwords.hash(password)
        return await self._users.create(normalize_email(email), password_hash, role, created_by)
