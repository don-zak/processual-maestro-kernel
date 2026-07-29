"""Pure commercial execution identity boundary for Maestro M1-R2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAttemptContext,
    MaestroExecutionAuthorityKind,
)

COMMERCIAL_EXECUTION_IDENTITY_VERSION = "maestro-commercial-execution-identity-m1-r2"
DISCOVERY_ONLY = True
RUNTIME_INTEGRATION_ENABLED = False
MEASUREMENT_EMISSION_ENABLED = False
SHADOW_STORE_WRITES_ENABLED = False
COMMERCIAL_ENFORCEMENT_ENABLED = False
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False
APPROVED_FOR_SETTLEMENT = False
LLM_CONNECTION_POLICY = "byok_only"
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
RAW_SECRETS_ALLOWED = False
RAW_PROMPTS_ALLOWED = False
RAW_RESPONSES_ALLOWED = False
SUPPORTED_COMMERCIAL_AUTHORITY_KINDS = (
    MaestroExecutionAuthorityKind.AGENT_RUNTIME,
)


class MaestroCommercialExecutionIdentityValidationError(ValueError):
    """Raised when a commercial identity is incomplete or unsafe."""


class MaestroCredentialOwnership(StrEnum):
    CUSTOMER_BYOK = "customer_byok"


@dataclass(frozen=True, slots=True)
class MaestroCommercialExecutionIdentity:
    context: MaestroExecutionAttemptContext
    tenant_reference: str
    credential_profile_reference: str
    workload_family_id: str
    credential_ownership: MaestroCredentialOwnership = (
        MaestroCredentialOwnership.CUSTOMER_BYOK
    )

    def __post_init__(self) -> None:
        if not isinstance(self.context, MaestroExecutionAttemptContext):
            raise MaestroCommercialExecutionIdentityValidationError(
                "context must be MaestroExecutionAttemptContext"
            )
        if self.context.authority_kind not in SUPPORTED_COMMERCIAL_AUTHORITY_KINDS:
            raise MaestroCommercialExecutionIdentityValidationError(
                "authority_kind is not approved for M1-R2 commercial identity"
            )
        if self.context.idempotency_key is None:
            raise MaestroCommercialExecutionIdentityValidationError(
                "commercial execution identity requires idempotency_key"
            )
        _require_identifier("tenant_reference", self.tenant_reference)
        _require_identifier(
            "credential_profile_reference",
            self.credential_profile_reference,
        )
        _require_identifier("workload_family_id", self.workload_family_id)
        if not isinstance(self.credential_ownership, MaestroCredentialOwnership):
            raise MaestroCommercialExecutionIdentityValidationError(
                "credential_ownership must be MaestroCredentialOwnership"
            )
        if self.credential_ownership is not MaestroCredentialOwnership.CUSTOMER_BYOK:
            raise MaestroCommercialExecutionIdentityValidationError(
                "commercial execution identity requires customer BYOK"
            )

    @property
    def execution_id(self) -> str:
        return self.context.execution_id

    @property
    def attempt_id(self) -> str:
        return self.context.attempt_id

    @property
    def authority_kind(self) -> MaestroExecutionAuthorityKind:
        return self.context.authority_kind

    @property
    def started_at(self):
        return self.context.started_at

    @property
    def retry_ordinal(self) -> int:
        return self.context.retry_ordinal

    @property
    def idempotency_key(self) -> str:
        value = self.context.idempotency_key
        if value is None:
            raise MaestroCommercialExecutionIdentityValidationError(
                "commercial execution identity requires idempotency_key"
            )
        return value

    @property
    def parent_execution_id(self) -> str | None:
        return self.context.parent_execution_id

    @property
    def stable_attempt_key(self) -> tuple[str, str, str]:
        return (self.tenant_reference, self.execution_id, self.attempt_id)


def _require_identifier(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise MaestroCommercialExecutionIdentityValidationError(
            f"{name} must be str"
        )
    if not value or len(value) > 128:
        raise MaestroCommercialExecutionIdentityValidationError(
            f"{name} must contain between 1 and 128 characters"
        )
    allowed = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789._:-"
    )
    if any(character not in allowed for character in value):
        raise MaestroCommercialExecutionIdentityValidationError(
            f"{name} contains unsupported characters"
        )
