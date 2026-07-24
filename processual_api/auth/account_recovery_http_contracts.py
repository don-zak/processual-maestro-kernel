from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _StrictContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class AccountRecoveryStartRequestContract(_StrictContractModel):
    login: str = Field(
        min_length=1,
        max_length=320,
    )


class AccountRecoveryStartAcceptedResponseContract(_StrictContractModel):
    status: str = "accepted"
    next_action: str = "check_recovery_email"


class AccountRecoveryVerifyRequestContract(_StrictContractModel):
    request_id: uuid.UUID
    token: str = Field(
        min_length=1,
        max_length=2048,
    )


class AccountRecoveryVerifiedResponseContract(_StrictContractModel):
    status: str = "verified"
    request_id: uuid.UUID
    completion_token: str
    completion_expires_at: datetime
    password_change_required: bool = True
    mfa_reenrollment_required: bool = True
    session_created: bool = False
    access_token_issued: bool = False
    refresh_token_issued: bool = False


__all__ = [
    "AccountRecoveryStartAcceptedResponseContract",
    "AccountRecoveryStartRequestContract",
    "AccountRecoveryVerifiedResponseContract",
    "AccountRecoveryVerifyRequestContract",
]
