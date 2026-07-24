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


class AccountRecoveryCompleteRequestContract(_StrictContractModel):
    request_id: uuid.UUID
    completion_token: str = Field(
        min_length=32,
        max_length=2048,
        repr=False,
    )
    new_password: str = Field(
        min_length=12,
        max_length=1024,
        repr=False,
    )
    confirm_password: str = Field(
        min_length=12,
        max_length=1024,
        repr=False,
    )

    def model_post_init(
        self,
        __context,
    ) -> None:
        if self.new_password != self.confirm_password:
            raise ValueError("Password confirmation does not match.")


class AccountRecoveryRevocationResponseContract(_StrictContractModel):
    sessions_revoked: int = Field(ge=0)
    refresh_tokens_revoked: int = Field(ge=0)
    action_tokens_revoked: int = Field(ge=0)
    supervisor_session_keys_revoked: int = Field(ge=0)
    api_keys_revoked: int = Field(ge=0)


class AccountRecoveryCompletedResponseContract(_StrictContractModel):
    status: str = "completed"
    request_id: uuid.UUID
    completed_at: datetime
    password_changed: bool = True
    mfa_reenrollment_required: bool = True
    revocations: AccountRecoveryRevocationResponseContract
    session_created: bool = False
    access_token_issued: bool = False
    refresh_token_issued: bool = False
    api_key_issued: bool = False
    authority_granted: bool = False


__all__ = [
    "AccountRecoveryCompletedResponseContract",
    "AccountRecoveryCompleteRequestContract",
    "AccountRecoveryRevocationResponseContract",
    "AccountRecoveryStartAcceptedResponseContract",
    "AccountRecoveryStartRequestContract",
    "AccountRecoveryVerifiedResponseContract",
    "AccountRecoveryVerifyRequestContract",
]
