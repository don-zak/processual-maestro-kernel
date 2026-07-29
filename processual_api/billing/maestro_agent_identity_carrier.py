"""Pure Agent Runtime identity carrier contract for Maestro M1-R3.

The carrier transports reference-only commercial identity metadata toward a
future Agent Runtime boundary. It does not import or invoke RuntimeAdapter,
execute agents, emit measurements, persist records, or authorize charging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from processual_api.billing.maestro_commercial_execution_identity import (
    MaestroCommercialExecutionIdentity,
)
from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAuthorityKind,
)

AGENT_IDENTITY_CARRIER_VERSION = "maestro-agent-identity-carrier-m1-r3"

DISCOVERY_ONLY = True
RUNTIME_INTEGRATION_ENABLED = False
AGENT_EXECUTION_ENABLED = False
MEASUREMENT_EMISSION_ENABLED = False
SHADOW_STORE_WRITES_ENABLED = False
COMMERCIAL_ENFORCEMENT_ENABLED = False
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False
APPROVED_FOR_SETTLEMENT = False

LLM_CONNECTION_POLICY = "byok_only"
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
RAW_TASK_CONTENT_ALLOWED = False
RAW_SECRETS_ALLOWED = False
RAW_PROMPTS_ALLOWED = False
RAW_RESPONSES_ALLOWED = False
RAW_AGENT_OUTPUT_ALLOWED = False


class MaestroAgentIdentityCarrierValidationError(ValueError):
    """Raised when an Agent Runtime identity carrier is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class MaestroAgentExecutionIdentityCarrier:
    """Reference-only carrier for a future Agent Runtime integration boundary."""

    identity: MaestroCommercialExecutionIdentity
    agent_reference: str
    task_reference: str
    requested_at: datetime
    correlation_reference: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.identity,
            MaestroCommercialExecutionIdentity,
        ):
            raise MaestroAgentIdentityCarrierValidationError("identity must be MaestroCommercialExecutionIdentity")

        if self.identity.authority_kind is not MaestroExecutionAuthorityKind.AGENT_RUNTIME:
            raise MaestroAgentIdentityCarrierValidationError("identity authority_kind must be AGENT_RUNTIME")

        _require_identifier("agent_reference", self.agent_reference)
        _require_identifier("task_reference", self.task_reference)
        _require_utc("requested_at", self.requested_at)

        if self.correlation_reference is not None:
            _require_identifier(
                "correlation_reference",
                self.correlation_reference,
            )

    @property
    def execution_id(self) -> str:
        return self.identity.execution_id

    @property
    def attempt_id(self) -> str:
        return self.identity.attempt_id

    @property
    def tenant_reference(self) -> str:
        return self.identity.tenant_reference

    @property
    def credential_profile_reference(self) -> str:
        return self.identity.credential_profile_reference

    @property
    def workload_family_id(self) -> str:
        return self.identity.workload_family_id

    @property
    def idempotency_key(self) -> str:
        return self.identity.idempotency_key

    @property
    def stable_carrier_key(self) -> tuple[str, str, str, str]:
        return (
            self.tenant_reference,
            self.execution_id,
            self.attempt_id,
            self.agent_reference,
        )

    def to_reference_payload(self) -> dict[str, object]:
        """Return only non-sensitive references suitable for a future boundary."""

        return {
            "execution_id": self.execution_id,
            "attempt_id": self.attempt_id,
            "tenant_reference": self.tenant_reference,
            "credential_profile_reference": self.credential_profile_reference,
            "workload_family_id": self.workload_family_id,
            "idempotency_key": self.idempotency_key,
            "agent_reference": self.agent_reference,
            "task_reference": self.task_reference,
            "requested_at": self.requested_at.isoformat(),
            "correlation_reference": self.correlation_reference,
        }


def _require_identifier(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise MaestroAgentIdentityCarrierValidationError(f"{name} must be str")

    if not value or len(value) > 128:
        raise MaestroAgentIdentityCarrierValidationError(f"{name} must contain between 1 and 128 characters")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")

    if any(character not in allowed for character in value):
        raise MaestroAgentIdentityCarrierValidationError(f"{name} contains unsupported characters")


def _require_utc(name: str, value: object) -> None:
    if not isinstance(value, datetime):
        raise MaestroAgentIdentityCarrierValidationError(f"{name} must be datetime")

    if value.tzinfo is None:
        raise MaestroAgentIdentityCarrierValidationError(f"{name} must be timezone-aware")

    if value.utcoffset() != UTC.utcoffset(value):
        raise MaestroAgentIdentityCarrierValidationError(f"{name} must use UTC")
