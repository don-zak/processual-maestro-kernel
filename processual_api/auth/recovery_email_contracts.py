from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StrictContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class RecoveryEmailVerificationRequestContract(
    _StrictContractModel
):
    token: str = Field(min_length=1, max_length=2048)


class RecoveryEmailVerificationAcceptedResponseContract(
    _StrictContractModel
):
    status: str = "accepted"
    next_action: str = "check_recovery_email"


class RecoveryEmailVerificationProcessedResponseContract(
    _StrictContractModel
):
    status: str = "processed"


__all__ = [
    "RecoveryEmailVerificationAcceptedResponseContract",
    "RecoveryEmailVerificationProcessedResponseContract",
    "RecoveryEmailVerificationRequestContract",
]
