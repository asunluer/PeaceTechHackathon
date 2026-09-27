"""User identity and authorization roles."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    VICTIM = "victim"
    NGO_INVESTIGATOR = "ngo_investigator"
    ADMINISTRATOR = "administrator"


@dataclass(frozen=True, slots=True)
class User:
    id: UUID
    email: str
    password_hash: str
    role: Role
    is_active: bool
    token_version: int
    created_at: datetime
