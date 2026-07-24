"""Strict contracts for platform account recovery.

AUTH-R9A deliberately separates recovery-email verification from account
recovery completion. Verifying control of a recovery address must never issue
an authenticated session, access token, refresh token, API key, or privileged
authority.

These contracts define only the transport and policy boundary. Persistence,
token issuance, revocation, and HTTP orchestration are implemented in later
AUTH-R9A layers.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

AccountRecoveryToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=32,
        max_length=2048,
    ),
]

AccountRecoveryPassword = Annotated[
    str,
    StringConstraints(
        min_length=12,
        max_length=1024,
    ),
]


class AccountRecoveryPurpose(StrEnum):
    """Purpose bound into account-recovery action tokens."""

    PLATFORM_ACCOUNT_RECOVERY = "platform_account_recovery"


class AccountRecoveryState(StrEnum):
    """Persistent account-recovery request lifecycle."""

    PENDING = "pending"
    VERIFIED = "verified"
    COMPLETED = "completed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class AccountRecoveryFailureCode(StrEnum):
    """Public, non-secret failure classifications."""

    INVALID_OR_EXPIRED = "invalid_or_expired"
    REPLAYED = "replayed"
    RECOVERY_EMAIL_UNAVAILABLE = "recovery_email_unavailable"
    ACCOUNT_NOT_ELIGIBLE = "account_not_eligible"
    PASSWORD_POLICY_REJECTED = "password_policy_rejected"
    MFA_REENROLLMENT_REQUIRED = "mfa_reenrollment_required"
    AUTHORITY_UNAVAILABLE = "authority_unavailable"
    RATE_LIMITED = "rate_limited"


class _StrictAccountRecoveryContract(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class AccountRecoveryStartRequestContract(_StrictAccountRecoveryContract):
    """Unauthenticated start request.

    The public response must remain enumeration resistant regardless of whether
    the supplied identity exists, is eligible, or has a verified recovery
    address.
    """

    email: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=320,
        ),
    ]


class AccountRecoveryStartResponseContract(_StrictAccountRecoveryContract):
    """Enumeration-resistant acknowledgement."""

    accepted: Literal[True] = True
    message: Literal[
        "If the account is eligible, recovery instructions will be sent."
    ] = "If the account is eligible, recovery instructions will be sent."


class AccountRecoveryVerifyRequestContract(_StrictAccountRecoveryContract):
    """Proof of control over the recovery address."""

    token: AccountRecoveryToken = Field(repr=False)


class AccountRecoveryVerifyResponseContract(_StrictAccountRecoveryContract):
    """Verification receipt that deliberately grants no authenticated state."""

    recovery_id: UUID
    state: Literal[AccountRecoveryState.VERIFIED]
    completion_token: AccountRecoveryToken = Field(repr=False)
    expires_at: datetime
    access_token_issued: Literal[False] = False
    refresh_token_issued: Literal[False] = False
    session_created: Literal[False] = False
    api_key_issued: Literal[False] = False
    authority_granted: Literal[False] = False


class AccountRecoveryCompleteRequestContract(_StrictAccountRecoveryContract):
    """Complete recovery with a purpose-bound, single-use token."""

    completion_token: AccountRecoveryToken = Field(repr=False)
    new_password: AccountRecoveryPassword = Field(repr=False)
    confirm_password: AccountRecoveryPassword = Field(repr=False)

    @model_validator(mode="after")
    def matching_passwords(self) -> AccountRecoveryCompleteRequestContract:
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password must match.")
        return self


class AccountRecoveryRevocationSummaryContract(_StrictAccountRecoveryContract):
    """Security consequences applied atomically with password replacement."""

    sessions_revoked: int = Field(ge=0)
    refresh_tokens_revoked: int = Field(ge=0)
    action_tokens_revoked: int = Field(ge=0)
    supervisor_session_keys_revoked: int = Field(ge=0)
    api_keys_revoked: int = Field(ge=0)


class AccountRecoveryCompleteResponseContract(_StrictAccountRecoveryContract):
    """Successful completion never signs the caller in."""

    recovery_id: UUID
    state: Literal[AccountRecoveryState.COMPLETED]
    completed_at: datetime
    password_changed: Literal[True] = True
    mfa_reenrollment_required: Literal[True] = True
    revocations: AccountRecoveryRevocationSummaryContract
    access_token_issued: Literal[False] = False
    refresh_token_issued: Literal[False] = False
    session_created: Literal[False] = False
    api_key_issued: Literal[False] = False
    authority_granted: Literal[False] = False


class AccountRecoveryProcessedResponseContract(_StrictAccountRecoveryContract):
    """Non-secret generic outcome used for invalid, expired, and replayed input."""

    processed: Literal[True] = True


class AccountRecoveryAuditEventContract(_StrictAccountRecoveryContract):
    """Safe audit projection.

    Raw tokens, passwords, recovery addresses, IP addresses, user agents, and
    cryptographic material are intentionally excluded.
    """

    event_id: UUID
    recovery_id: UUID | None = None
    user_id: UUID | None = None
    action: Literal[
        "start",
        "verify",
        "complete",
        "expire",
        "revoke",
    ]
    result: Literal[
        "accepted",
        "processed",
        "completed",
        "denied",
        "rate_limited",
        "authority_unavailable",
    ]
    occurred_at: datetime
    failure_code: AccountRecoveryFailureCode | None = None


__all__ = [
    "AccountRecoveryAuditEventContract",
    "AccountRecoveryCompleteRequestContract",
    "AccountRecoveryCompleteResponseContract",
    "AccountRecoveryFailureCode",
    "AccountRecoveryPassword",
    "AccountRecoveryProcessedResponseContract",
    "AccountRecoveryPurpose",
    "AccountRecoveryRevocationSummaryContract",
    "AccountRecoveryStartRequestContract",
    "AccountRecoveryStartResponseContract",
    "AccountRecoveryState",
    "AccountRecoveryToken",
    "AccountRecoveryVerifyRequestContract",
    "AccountRecoveryVerifyResponseContract",
]
