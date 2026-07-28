"""Fail-closed evidence catalog for known Maestro execution families.

This module records discovery evidence only. It does not integrate with
runtime paths, emit measurements, persist records, mutate entitlements, or
authorize commercial use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAuthorityKind,
)
from processual_api.billing.maestro_execution_authority_readiness import (
    MaestroExecutionAuthorityReadiness,
    MaestroReadinessCapabilityStatus,
)

EXECUTION_FAMILY_EVIDENCE_VERSION = "maestro-execution-family-evidence-m1-r1"

DISCOVERY_ONLY = True
RUNTIME_INTEGRATION_ENABLED = False
MEASUREMENT_EMISSION_ENABLED = False
COMMERCIAL_ENFORCEMENT_ENABLED = False
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False
APPROVED_FOR_SETTLEMENT = False

LLM_CONNECTION_POLICY = "byok_only"
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False


class MaestroExecutionFamilyEvidenceValidationError(ValueError):
    """Raised when execution-family evidence is incomplete or unsafe."""


class MaestroExecutionEvidenceClassification(StrEnum):
    PRODUCTION = "production"
    PARTIAL_PRODUCTION = "partial_production"
    ABSTRACT_CONTRACT = "abstract_contract"
    SYNTHETIC_ONLY = "synthetic_only"


class MaestroCommercialWorkloadClassification(StrEnum):
    NON_BILLABLE_PLATFORM = "non_billable_platform"
    COMMERCIAL_CANDIDATE = "commercial_candidate"
    NOT_ELIGIBLE = "not_eligible"


@dataclass(frozen=True, slots=True)
class MaestroExecutionFamilyEvidence:
    family_id: str
    authority_kind: MaestroExecutionAuthorityKind
    evidence_classification: MaestroExecutionEvidenceClassification
    commercial_classification: MaestroCommercialWorkloadClassification
    readiness: MaestroExecutionAuthorityReadiness
    entrypoint_references: tuple[str, ...]
    completion_references: tuple[str, ...]
    retry_owner_reference: str | None
    idempotency_reference: str | None
    missing_capabilities: tuple[str, ...]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_identifier("family_id", self.family_id)

        if not isinstance(self.authority_kind, MaestroExecutionAuthorityKind):
            raise MaestroExecutionFamilyEvidenceValidationError("authority_kind must be MaestroExecutionAuthorityKind")

        if not isinstance(
            self.evidence_classification,
            MaestroExecutionEvidenceClassification,
        ):
            raise MaestroExecutionFamilyEvidenceValidationError(
                "evidence_classification must be MaestroExecutionEvidenceClassification"
            )

        if not isinstance(
            self.commercial_classification,
            MaestroCommercialWorkloadClassification,
        ):
            raise MaestroExecutionFamilyEvidenceValidationError(
                "commercial_classification must be MaestroCommercialWorkloadClassification"
            )

        if not isinstance(self.readiness, MaestroExecutionAuthorityReadiness):
            raise MaestroExecutionFamilyEvidenceValidationError("readiness must be MaestroExecutionAuthorityReadiness")

        if self.readiness.authority_kind is not self.authority_kind:
            raise MaestroExecutionFamilyEvidenceValidationError(
                "readiness authority_kind must match evidence authority_kind"
            )

        _require_reference_tuple(
            "entrypoint_references",
            self.entrypoint_references,
            allow_empty=False,
        )
        _require_reference_tuple(
            "completion_references",
            self.completion_references,
            allow_empty=True,
        )
        _require_optional_reference(
            "retry_owner_reference",
            self.retry_owner_reference,
        )
        _require_optional_reference(
            "idempotency_reference",
            self.idempotency_reference,
        )
        _require_reference_tuple(
            "missing_capabilities",
            self.missing_capabilities,
            allow_empty=True,
        )
        _require_reference_tuple("notes", self.notes, allow_empty=True)

        if len(set(self.missing_capabilities)) != len(self.missing_capabilities):
            raise MaestroExecutionFamilyEvidenceValidationError("missing_capabilities must not contain duplicates")

        if (
            self.evidence_classification is MaestroExecutionEvidenceClassification.SYNTHETIC_ONLY
            and self.commercial_classification is MaestroCommercialWorkloadClassification.COMMERCIAL_CANDIDATE
        ):
            raise MaestroExecutionFamilyEvidenceValidationError(
                "synthetic-only evidence cannot be a commercial candidate"
            )

    @property
    def commercial_measurement_ready(self) -> bool:
        return (
            self.evidence_classification is MaestroExecutionEvidenceClassification.PRODUCTION
            and self.commercial_classification is MaestroCommercialWorkloadClassification.COMMERCIAL_CANDIDATE
            and self.readiness.is_ready
            and not self.missing_capabilities
        )


def _require_identifier(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must be str")

    if not value or len(value) > 128:
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must contain between 1 and 128 characters")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")

    if any(character not in allowed for character in value):
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} contains unsupported characters")


def _require_optional_reference(name: str, value: object) -> None:
    if value is None:
        return

    if not isinstance(value, str):
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must be str or None")

    if not value.strip() or len(value) > 512:
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must contain between 1 and 512 characters")


def _require_reference_tuple(
    name: str,
    value: object,
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(value, tuple):
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must be tuple")

    if not allow_empty and not value:
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must not be empty")

    if len(set(value)) != len(value):
        raise MaestroExecutionFamilyEvidenceValidationError(f"{name} must not contain duplicates")

    for item in value:
        if not isinstance(item, str):
            raise MaestroExecutionFamilyEvidenceValidationError(f"{name} items must be str")

        if not item.strip() or len(item) > 512:
            raise MaestroExecutionFamilyEvidenceValidationError(
                f"{name} items must contain between 1 and 512 characters"
            )


SUPPORTED = MaestroReadinessCapabilityStatus.SUPPORTED
UNSUPPORTED = MaestroReadinessCapabilityStatus.UNSUPPORTED
UNKNOWN = MaestroReadinessCapabilityStatus.UNKNOWN
SYNTHETIC_ONLY = MaestroReadinessCapabilityStatus.SYNTHETIC_ONLY


AUTH_DELIVERY_READINESS = MaestroExecutionAuthorityReadiness(
    authority_kind=MaestroExecutionAuthorityKind.DELIVERY_DISPATCH,
    execution_id=SUPPORTED,
    attempt_id=SUPPORTED,
    retry_ordinal=SUPPORTED,
    idempotency_key=SUPPORTED,
    start_event=SUPPORTED,
    completion_event=SUPPORTED,
    completion_outcomes=SUPPORTED,
    structured_usage=UNSUPPORTED,
    failure_ownership=SUPPORTED,
    production_classification=SUPPORTED,
    best_effort_observation=UNKNOWN,
    tenant_reference=SUPPORTED,
    credential_profile_reference=UNSUPPORTED,
)

AGENT_RUNTIME_READINESS = MaestroExecutionAuthorityReadiness(
    authority_kind=MaestroExecutionAuthorityKind.AGENT_RUNTIME,
    execution_id=UNSUPPORTED,
    attempt_id=UNSUPPORTED,
    retry_ordinal=UNKNOWN,
    idempotency_key=UNKNOWN,
    start_event=UNKNOWN,
    completion_event=SUPPORTED,
    completion_outcomes=SUPPORTED,
    structured_usage=UNKNOWN,
    failure_ownership=UNKNOWN,
    production_classification=UNKNOWN,
    best_effort_observation=UNKNOWN,
    tenant_reference=UNKNOWN,
    credential_profile_reference=UNKNOWN,
)

LLM_ADAPTER_READINESS = MaestroExecutionAuthorityReadiness(
    authority_kind=MaestroExecutionAuthorityKind.LLM_ADAPTER,
    execution_id=UNSUPPORTED,
    attempt_id=UNSUPPORTED,
    retry_ordinal=UNKNOWN,
    idempotency_key=UNKNOWN,
    start_event=SUPPORTED,
    completion_event=SUPPORTED,
    completion_outcomes=SUPPORTED,
    structured_usage=UNSUPPORTED,
    failure_ownership=UNKNOWN,
    production_classification=SUPPORTED,
    best_effort_observation=UNKNOWN,
    tenant_reference=UNKNOWN,
    credential_profile_reference=UNKNOWN,
)

CONNECTOR_SANDBOX_READINESS = MaestroExecutionAuthorityReadiness(
    authority_kind=MaestroExecutionAuthorityKind.CONNECTOR_RUNTIME,
    execution_id=SYNTHETIC_ONLY,
    attempt_id=UNSUPPORTED,
    retry_ordinal=SYNTHETIC_ONLY,
    idempotency_key=SYNTHETIC_ONLY,
    start_event=SYNTHETIC_ONLY,
    completion_event=SYNTHETIC_ONLY,
    completion_outcomes=SYNTHETIC_ONLY,
    structured_usage=UNSUPPORTED,
    failure_ownership=SYNTHETIC_ONLY,
    production_classification=SYNTHETIC_ONLY,
    best_effort_observation=UNKNOWN,
    tenant_reference=SYNTHETIC_ONLY,
    credential_profile_reference=UNSUPPORTED,
)


AUTH_DELIVERY_EVIDENCE = MaestroExecutionFamilyEvidence(
    family_id="auth.delivery_dispatch",
    authority_kind=MaestroExecutionAuthorityKind.DELIVERY_DISPATCH,
    evidence_classification=MaestroExecutionEvidenceClassification.PRODUCTION,
    commercial_classification=(MaestroCommercialWorkloadClassification.NON_BILLABLE_PLATFORM),
    readiness=AUTH_DELIVERY_READINESS,
    entrypoint_references=("processual_api.auth.delivery_dispatcher.DeliveryDispatcher.dispatch_once",),
    completion_references=(
        "processual_api.auth.delivery_dispatcher.DeliveryRepository.mark_delivered",
        "processual_api.auth.delivery_dispatcher.DeliveryRepository.mark_failed",
    ),
    retry_owner_reference=("processual_api.auth.delivery_dispatcher.DeliveryDispatcher"),
    idempotency_reference=("processual_api.auth.delivery_dispatcher.DeliveryDispatcher._idempotency_key"),
    missing_capabilities=(
        "structured_usage",
        "best_effort_observation",
        "credential_profile_reference",
    ),
    notes=(
        "Production reference authority.",
        "Internal platform workload.",
        "Must remain outside customer charging.",
    ),
)

AGENT_RUNTIME_EVIDENCE = MaestroExecutionFamilyEvidence(
    family_id="agent.runtime_adapter",
    authority_kind=MaestroExecutionAuthorityKind.AGENT_RUNTIME,
    evidence_classification=(MaestroExecutionEvidenceClassification.ABSTRACT_CONTRACT),
    commercial_classification=(MaestroCommercialWorkloadClassification.COMMERCIAL_CANDIDATE),
    readiness=AGENT_RUNTIME_READINESS,
    entrypoint_references=("processual_api.adapters.agent_runtime.RuntimeAdapter.run_agent",),
    completion_references=("processual_api.adapters.agent_runtime.AgentExecutionResult",),
    retry_owner_reference=None,
    idempotency_reference=None,
    missing_capabilities=(
        "execution_id",
        "attempt_id",
        "retry_ordinal",
        "idempotency_key",
        "start_event",
        "structured_usage",
        "failure_ownership",
        "production_classification",
        "best_effort_observation",
        "tenant_reference",
        "credential_profile_reference",
    ),
    notes=(
        "Abstract adapter boundary only.",
        "No unified production attempt authority is established.",
    ),
)

LLM_ADAPTER_EVIDENCE = MaestroExecutionFamilyEvidence(
    family_id="cgt_governor.llm_adapter",
    authority_kind=MaestroExecutionAuthorityKind.LLM_ADAPTER,
    evidence_classification=(MaestroExecutionEvidenceClassification.PARTIAL_PRODUCTION),
    commercial_classification=(MaestroCommercialWorkloadClassification.COMMERCIAL_CANDIDATE),
    readiness=LLM_ADAPTER_READINESS,
    entrypoint_references=(
        "processual_api.cgt_governor.adapters.base.BaseLLMAdapter.generate",
        "processual_api.routers.cgt_governor.generate_repair",
        "processual_api.routers.cgt_governor.auto_repair",
        "processual_api.routers.cgt_governor.compare_adapters",
    ),
    completion_references=("processual_api.cgt_governor.adapters.base.BaseLLMAdapter.generate",),
    retry_owner_reference=None,
    idempotency_reference=None,
    missing_capabilities=(
        "execution_id",
        "attempt_id",
        "retry_ordinal",
        "idempotency_key",
        "structured_usage",
        "failure_ownership",
        "best_effort_observation",
        "tenant_reference",
        "credential_profile_reference",
    ),
    notes=(
        "Live execution paths exist.",
        "Execution ownership remains distributed.",
        "BYOK-only policy remains mandatory.",
    ),
)

CONNECTOR_SANDBOX_EVIDENCE = MaestroExecutionFamilyEvidence(
    family_id="integrations.connector_sandbox_read",
    authority_kind=MaestroExecutionAuthorityKind.CONNECTOR_RUNTIME,
    evidence_classification=(MaestroExecutionEvidenceClassification.SYNTHETIC_ONLY),
    commercial_classification=(MaestroCommercialWorkloadClassification.NOT_ELIGIBLE),
    readiness=CONNECTOR_SANDBOX_READINESS,
    entrypoint_references=(
        "processual_api.integrations.sandbox_read_workflow.execute_connector_sandbox_read_workflow",
        "processual_api.integrations.mock_dispatcher.ConnectorMockDispatcher.dispatch",
    ),
    completion_references=(
        "processual_api.integrations.sandbox_read_workflow.ConnectorSandboxReadWorkflowResult",
        "processual_api.integrations.mock_dispatcher.ConnectorDispatchResult",
    ),
    retry_owner_reference=None,
    idempotency_reference=("processual_api.integrations.mock_dispatcher.ConnectorDispatchRequest.idempotency_key"),
    missing_capabilities=(
        "production_execution",
        "attempt_id",
        "structured_usage",
        "credential_profile_reference",
    ),
    notes=(
        "Deterministic local safety workflow.",
        "No production connector execution occurs.",
    ),
)


EXECUTION_FAMILY_EVIDENCE_CATALOG = (
    AUTH_DELIVERY_EVIDENCE,
    AGENT_RUNTIME_EVIDENCE,
    LLM_ADAPTER_EVIDENCE,
    CONNECTOR_SANDBOX_EVIDENCE,
)


def get_execution_family_evidence(
    family_id: str,
) -> MaestroExecutionFamilyEvidence | None:
    _require_identifier("family_id", family_id)

    for evidence in EXECUTION_FAMILY_EVIDENCE_CATALOG:
        if evidence.family_id == family_id:
            return evidence

    return None


def commercial_measurement_ready_families() -> tuple[MaestroExecutionFamilyEvidence, ...]:
    return tuple(evidence for evidence in EXECUTION_FAMILY_EVIDENCE_CATALOG if evidence.commercial_measurement_ready)
