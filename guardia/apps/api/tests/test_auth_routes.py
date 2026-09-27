"""Exercise the authentication HTTP contract without a database server."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import get_auth_service
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.application.auth import AuthService, DuplicateEmail
from app.core.config import Settings
from app.domain.users import Role, User
from app.infrastructure.security import Argon2PasswordHasher, PyJwtTokenCodec


class MemoryUsers:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def has_administrator(self) -> bool:
        return any(user.role == Role.ADMINISTRATOR for user in self.users.values())

    async def create(self, email: str, password_hash: str, role: Role, created_by: UUID | None = None, self_registered: bool = False) -> User:
        if await self.get_by_email(email):
            raise DuplicateEmail
        user = User(uuid4(), email, password_hash, role, True, 0, datetime.now(timezone.utc))
        self.users[user.id] = user
        return user

    async def revoke_tokens(self, user_id: UUID) -> None:
        self.users[user_id] = replace(self.users[user_id], token_version=self.users[user_id].token_version + 1)

    async def change_password(self, user_id: UUID, password_hash: str) -> None:
        self.users[user_id] = replace(self.users[user_id], password_hash=password_hash, token_version=self.users[user_id].token_version + 1)


def test_authentication_and_role_guard_http_flow() -> None:
    settings = Settings(
        db_host="localhost",
        db_name="test",
        db_user="test",
        db_password=SecretStr("test-password"),
        jwt_secret=SecretStr("a-dedicated-test-secret-with-more-than-32-bytes"),
    )
    service = AuthService(MemoryUsers(), Argon2PasswordHasher(), PyJwtTokenCodec(settings))
    administrator = asyncio.run(service.create_first_administrator("admin@example.org", "administrator-password"))
    asyncio.run(service.create_user(administrator, "admin@guardia.local", "local-test-password", Role.ADMINISTRATOR))

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.dependency_overrides[get_auth_service] = lambda: service

    with TestClient(app) as client:
        token_url = "/api/v1/auth/token"
        assert client.post(token_url, data={"username": "admin@example.org", "password": "wrong"}).status_code == 401

        response = client.post(
            token_url,
            data={"username": "admin@example.org", "password": "administrator-password"},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        admin_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        assert client.get("/api/v1/auth/me", headers=admin_headers).json()["role"] == "administrator"
        local_token = client.post(token_url, data={"username": "admin@guardia.local", "password": "local-test-password"}).json()["access_token"]
        local_account = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {local_token}"})
        assert local_account.status_code == 200
        assert local_account.json()["email"] == "admin@guardia.local"

        new_user = {"email": "investigator@example.org", "password": "investigator-password", "role": "ngo_investigator"}
        response = client.post("/api/v1/users", json=new_user, headers=admin_headers)
        assert response.status_code == 201
        assert response.json()["email"] == new_user["email"]
        assert "password_hash" not in response.json()
        assert client.post("/api/v1/users", json=new_user, headers=admin_headers).status_code == 409

        investigator_token = client.post(
            token_url,
            data={"username": new_user["email"], "password": new_user["password"]},
        ).json()["access_token"]
        investigator_headers = {"Authorization": f"Bearer {investigator_token}"}
        assert client.post("/api/v1/users", json=new_user, headers=investigator_headers).status_code == 403
        assert client.post("/api/v1/auth/logout", headers=admin_headers).status_code == 204
        assert client.get("/api/v1/auth/me", headers=admin_headers).status_code == 401
        assert client.get("/api/v1/auth/me", headers=investigator_headers).status_code == 200
        assert client.post("/api/v1/auth/change-password", headers=investigator_headers, json={"current_password": "wrong", "new_password": "new-investigator-password"}).status_code == 400
        assert client.post("/api/v1/auth/change-password", headers=investigator_headers, json={"current_password": new_user["password"], "new_password": "new-investigator-password"}).status_code == 204
        assert client.get("/api/v1/auth/me", headers=investigator_headers).status_code == 401
        assert client.post(token_url, data={"username": new_user["email"], "password": "new-investigator-password"}).status_code == 200


def test_self_registration_always_creates_a_victim() -> None:
    settings = Settings(
        db_host="localhost",
        db_name="test",
        db_user="test",
        db_password=SecretStr("test-password"),
        jwt_secret=SecretStr("a-dedicated-test-secret-with-more-than-32-bytes"),
    )
    service = AuthService(MemoryUsers(), Argon2PasswordHasher(), PyJwtTokenCodec(settings))
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.dependency_overrides[get_auth_service] = lambda: service

    with TestClient(app) as client:
        register_url = "/api/v1/auth/register"
        response = client.post(register_url, json={"email": "  Survivor@Example.org ", "password": "a-long-enough-password"})
        assert response.status_code == 201, response.text
        assert response.headers["cache-control"] == "no-store"
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        account = client.get("/api/v1/auth/me", headers=headers).json()
        assert account["role"] == "victim"
        assert account["email"] == "survivor@example.org"

        assert client.post(register_url, json={"email": "survivor@example.org", "password": "another-long-password"}).status_code == 409
        assert client.post(register_url, json={"email": "short@example.org", "password": "too-short"}).status_code == 422
        assert client.post(register_url, json={"email": "not-an-email", "password": "a-long-enough-password"}).status_code == 422
        escalation = client.post(register_url, json={"email": "staff@example.org", "password": "a-long-enough-password", "role": "administrator"})
        assert escalation.status_code == 422
        assert client.post("/api/v1/auth/token", data={"username": "staff@example.org", "password": "a-long-enough-password"}).status_code == 401
