"""Create the first administrator with a password entered at the terminal."""

import argparse
import asyncio
import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.application.auth import AdministratorExists, AuthService, DuplicateEmail
from app.core.config import get_settings
from app.infrastructure.database import Database
from app.infrastructure.security import PyJwtTokenCodec, get_password_hasher
from app.infrastructure.user_repository import SqlAlchemyUserRepository


async def create_administrator(email: str, password: str) -> None:
    database = Database(get_settings())
    try:
        async with database.sessions() as session:
            auth = AuthService(
                SqlAlchemyUserRepository(session),
                get_password_hasher(),
                PyJwtTokenCodec(get_settings()),
            )
            await auth.create_first_administrator(email, password)
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first SAFE-ARCHIVE administrator")
    parser.add_argument("--email", required=True, help="Administrator email address")
    args = parser.parse_args()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email))
    except ValidationError as exc:
        parser.error(str(exc))
    password = getpass.getpass("Password (12–128 characters): ")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        asyncio.run(create_administrator(email, password))
    except (AdministratorExists, DuplicateEmail, ValueError) as exc:
        parser.error(str(exc) or type(exc).__name__)
    print(f"Administrator created: {email}")


if __name__ == "__main__":
    main()
