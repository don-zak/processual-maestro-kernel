from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _StrictMfaContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MfaEnrollmentRequestContract(_StrictMfaContract):
    label: str = Field(default="Authenticator", min_length=1, max_length=80)


class MfaEnrollmentResponseContract(_StrictMfaContract):
    secret: str
    provisioning_uri: str


class MfaCodeRequestContract(_StrictMfaContract):
    code: str = Field(min_length=6, max_length=8)


class MfaVerificationRequestContract(_StrictMfaContract):
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=64)

    @model_validator(mode="after")
    def exactly_one_credential(self) -> MfaVerificationRequestContract:
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError("Exactly one MFA credential is required.")
        return self


class MfaRecoveryCodesResponseContract(_StrictMfaContract):
    recovery_codes: tuple[str, ...]


class MfaStatusResponseContract(_StrictMfaContract):
    enabled: bool
    pending_enrollment: bool
    recovery_codes_remaining: int
    step_up_satisfied: bool


class MfaProcessedResponseContract(_StrictMfaContract):
    status: str = "processed"


@dataclass(frozen=True, slots=True)
class MfaStatus:
    enabled: bool
    pending_enrollment: bool
    recovery_codes_remaining: int
    step_up_satisfied: bool


@dataclass(frozen=True, slots=True)
class MfaEnrollment:
    secret: str
    provisioning_uri: str


__all__ = [
    "MfaCodeRequestContract",
    "MfaEnrollment",
    "MfaEnrollmentRequestContract",
    "MfaEnrollmentResponseContract",
    "MfaProcessedResponseContract",
    "MfaRecoveryCodesResponseContract",
    "MfaStatus",
    "MfaStatusResponseContract",
    "MfaVerificationRequestContract",
]
