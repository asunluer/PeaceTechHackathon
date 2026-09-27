"""Validated configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAFE_ARCHIVE_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    db_host: str
    db_name: str
    db_user: str
    db_password: SecretStr
    jwt_secret: SecretStr
    access_token_minutes: int = 15
    storage_root: Path = Path("/data/evidence")
    storage_encryption_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    capture_proxy_url: str | None = None

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("JWT secret must contain at least 32 bytes")
        return value

    @field_validator("access_token_minutes")
    @classmethod
    def validate_token_lifetime(cls, value: int) -> int:
        if not 1 <= value <= 60:
            raise ValueError("Access token lifetime must be between 1 and 60 minutes")
        return value

    @field_validator("storage_encryption_key")
    @classmethod
    def validate_storage_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value().encode("utf-8")) != 32:
            raise ValueError("Storage encryption key must contain exactly 32 UTF-8 bytes")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
