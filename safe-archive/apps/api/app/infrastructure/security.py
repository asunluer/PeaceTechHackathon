"""Argon2 password hashing and strictly validated HS256 access tokens."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID, uuid4

import jwt
from anyio import to_thread
from pwdlib import PasswordHash

from app.application.auth import InvalidAccessToken
from app.application.ports import AccessToken, TokenIdentity
from app.core.config import Settings
from app.domain.users import User

ISSUER = "safe-archive"
AUDIENCE = "safe-archive-api"


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash("not-a-real-account-password")

    async def hash(self, password: str) -> str:
        return await to_thread.run_sync(self._hasher.hash, password)

    async def verify(self, password: str, password_hash: str | None) -> bool:
        candidate = password_hash or self._dummy_hash
        result = await to_thread.run_sync(self._hasher.verify, password, candidate)
        return bool(password_hash) and result


@lru_cache
def get_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


class PyJwtTokenCodec:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret.get_secret_value()
        self._lifetime = timedelta(minutes=settings.access_token_minutes)

    def issue(self, user: User) -> AccessToken:
        now = datetime.now(timezone.utc)
        claims = {
            "sub": str(user.id),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": now + self._lifetime,
            "jti": str(uuid4()),
            "typ": "access",
            "ver": user.token_version,
        }
        return AccessToken(
            value=jwt.encode(claims, self._secret, algorithm="HS256"),
            expires_in=int(self._lifetime.total_seconds()),
        )

    def decode(self, value: str) -> TokenIdentity:
        try:
            claims = jwt.decode(
                value,
                self._secret,
                algorithms=["HS256"],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti"]},
                leeway=5,
            )
            version = claims.get("ver")
            if claims.get("typ") != "access" or type(version) is not int or version < 0:
                raise InvalidAccessToken
            return TokenIdentity(user_id=UUID(claims["sub"]), token_version=version)
        except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
            raise InvalidAccessToken from exc
