from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequestContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class AccessTokenResponseContract(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    mfa_required: bool | None = None


class SessionProcessedResponseContract(BaseModel):
    status: str = "processed"


class SessionViewContract(BaseModel):
    id: uuid.UUID
    authenticated_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime
    current: bool


class SessionListResponseContract(BaseModel):
    sessions: tuple[SessionViewContract, ...]


@dataclass(frozen=True, slots=True)
class IssuedSession:
    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_expires_in: int
    csrf_token: str
    session_id: uuid.UUID
    mfa_required: bool = False


@dataclass(frozen=True, slots=True)
class SessionView:
    id: uuid.UUID
    authenticated_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime


__all__ = [
    "AccessTokenResponseContract",
    "IssuedSession",
    "LoginRequestContract",
    "SessionListResponseContract",
    "SessionProcessedResponseContract",
    "SessionView",
    "SessionViewContract",
]
