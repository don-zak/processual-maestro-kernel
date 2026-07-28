from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAuthorityKind,
)

EXECUTION_AUTHORITY_READINESS_VERSION = "maestro-execution-authority-readiness-r2c"

DISCOVERY_ONLY = True
RUNTIME_INTEGRATION_ENABLED = False
MEASUREMENT_EMISSION_ENABLED = False
COMMERCIAL_ENFORCEMENT_ENABLED = False

LLM_CONNECTION_POLICY = "byok_only"
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
RAW_SECRETS_ALLOWED = False
RAW_PROMPTS_ALLOWED = False
RAW_RESPONSES_ALLOWED = False


class MaestroExecutionAuthorityReadinessValidationError(ValueError):
    """Raised when readiness evidence is incomplete or unsafe."""


class MaestroReadinessCapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"
    SYNTHETIC_ONLY = "synthetic_only"


@dataclass(frozen=True, slots=True)
class MaestroExecutionAuthorityReadiness:
    authority_kind: MaestroExecutionAuthorityKind
    execution_id: MaestroReadinessCapabilityStatus
    attempt_id: MaestroReadinessCapabilityStatus
    retry_ordinal: MaestroReadinessCapabilityStatus
    idempotency_key: MaestroReadinessCapabilityStatus
    start_event: MaestroReadinessCapabilityStatus
    completion_event: MaestroReadinessCapabilityStatus
    completion_outcomes: MaestroReadinessCapabilityStatus
    structured_usage: MaestroReadinessCapabilityStatus
    failure_ownership: MaestroReadinessCapabilityStatus
    production_classification: MaestroReadinessCapabilityStatus
    best_effort_observation: MaestroReadinessCapabilityStatus
    tenant_reference: MaestroReadinessCapabilityStatus
    credential_profile_reference: MaestroReadinessCapabilityStatus

    def __post_init__(self) -> None:
        if not isinstance(
            self.authority_kind,
            MaestroExecutionAuthorityKind,
        ):
            raise MaestroExecutionAuthorityReadinessValidationError(
                "authority_kind must be MaestroExecutionAuthorityKind"
            )

        for field_name in _CAPABILITY_FIELDS:
            value = getattr(self, field_name)

            if not isinstance(
                value,
                MaestroReadinessCapabilityStatus,
            ):
                raise MaestroExecutionAuthorityReadinessValidationError(
                    f"{field_name} must be MaestroReadinessCapabilityStatus"
                )

    @property
    def is_ready(self) -> bool:
        return all(
            getattr(self, field_name) is MaestroReadinessCapabilityStatus.SUPPORTED for field_name in _CAPABILITY_FIELDS
        )


_CAPABILITY_FIELDS = (
    "execution_id",
    "attempt_id",
    "retry_ordinal",
    "idempotency_key",
    "start_event",
    "completion_event",
    "completion_outcomes",
    "structured_usage",
    "failure_ownership",
    "production_classification",
    "best_effort_observation",
    "tenant_reference",
    "credential_profile_reference",
)
