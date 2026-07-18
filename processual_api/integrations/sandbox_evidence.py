"""Immutable reference-only sandbox evidence contracts.

R7 accepts completed R5 workflow results or R6 deterministic fault results
as source objects. The evidence layer does not invoke either source workflow,
a transport, dispatcher, secret manager, network, runtime, route, exporter,
background task, persistence layer, or production connector.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.sandbox_read_faults import (
    ConnectorSandboxReadFaultResult,
)
from processual_api.integrations.sandbox_read_workflow import (
    ConnectorSandboxReadWorkflowResult,
)

__all__ = [
    "CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS",
    "SUPPORTED_CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS",
    "ConnectorSandboxEvidenceAssessment",
    "ConnectorSandboxEvidenceBundle",
    "ConnectorSandboxEvidenceBundleStatus",
    "ConnectorSandboxEvidenceContract",
    "ConnectorSandboxEvidenceContractStatus",
    "ConnectorSandboxEvidenceRequest",
    "ConnectorSandboxEvidenceSourceKind",
    "assess_connector_sandbox_evidence_contract",
    "build_connector_sandbox_evidence_bundle",
    "get_connector_sandbox_evidence_contract",
    "list_connector_sandbox_evidence_contracts",
    "normalize_connector_sandbox_evidence_contract_id",
    "validate_connector_sandbox_evidence_contracts",
    "validate_connector_sandbox_evidence_registry",
]


class ConnectorSandboxEvidenceSourceKind(StrEnum):
    WORKFLOW_RESULT = "sandbox_read_workflow_result"
    FAULT_RESULT = "sandbox_read_fault_result"


class ConnectorSandboxEvidenceContractStatus(StrEnum):
    LOCAL_EVIDENCE_READY = "local_evidence_ready"
    BLOCKED = "blocked"


class ConnectorSandboxEvidenceBundleStatus(StrEnum):
    EVIDENCE_CAPTURED = "evidence_captured"
    INVALID_SOURCE_RESULT = "invalid_source_result"
    UNSAFE_SOURCE_REJECTED = "unsafe_source_rejected"
    CONTRACT_BLOCKED = "contract_blocked"


_EVIDENCE_CONTRACT_ID: Final[str] = (
    "telecom_ticketing_local_sandbox_evidence_contract"
)
_WORKFLOW_ID: Final[str] = (
    "telecom_ticketing_deterministic_sandbox_read_workflow"
)

_REQUIRED_TRUE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "local_only",
    "sandbox_only",
    "reference_only",
    "deterministic",
    "immutable_bundle_required",
    "non_persistent_by_default",
    "export_safe_references_only",
    "source_validation_required",
    "unsafe_flag_projection_required",
)

_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "source_execution_allowed",
    "payload_body_allowed",
    "raw_response_allowed",
    "secret_material_allowed",
    "credential_resolution_allowed",
    "dispatcher_invocation_allowed",
    "network_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "external_export_execution_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
)

_UNSAFE_BUNDLE_FLAGS: Final[tuple[str, ...]] = (
    "source_executed",
    "payload_body_included",
    "raw_response_included",
    "secret_material_included",
    "credentials_resolved",
    "dispatcher_invoked",
    "network_accessed",
    "bundle_persisted",
    "background_task_created",
    "external_export_executed",
    "route_exposed",
    "runtime_used",
    "production_used",
)

_PROHIBITED_REFERENCE_MARKERS: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "bearer ",
    "password=",
    "token=",
    "secret=",
    "private_key=",
    "raw_payload=",
    "response_body=",
)


def _validate_reference(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string reference.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{name} must not be empty.")

    if normalized != value:
        raise ValueError(
            f"{name} must not contain surrounding whitespace."
        )

    lowered = normalized.lower()

    if any(
        marker in lowered
        for marker in _PROHIBITED_REFERENCE_MARKERS
    ):
        raise ValueError(
            f"{name} contains prohibited raw material."
        )

    return normalized


def _validate_reference_tuple(
    name: str,
    values: object,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple.")

    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates.")

    for index, value in enumerate(values):
        _validate_reference(
            f"{name}[{index}]",
            value,
        )

    return values


def normalize_connector_sandbox_evidence_contract_id(
    evidence_contract_id: str,
) -> str:
    return _validate_reference(
        "evidence_contract_id",
        evidence_contract_id,
    )


@dataclass(frozen=True, slots=True)
class ConnectorSandboxEvidenceContract:
    evidence_contract_id: str
    workflow_id: str
    source_type_references: tuple[str, ...]
    bundle_type_reference: str
    output_mode_reference: str
    local_only: bool = True
    sandbox_only: bool = True
    reference_only: bool = True
    deterministic: bool = True
    immutable_bundle_required: bool = True
    non_persistent_by_default: bool = True
    export_safe_references_only: bool = True
    source_validation_required: bool = True
    unsafe_flag_projection_required: bool = True
    status: ConnectorSandboxEvidenceContractStatus = (
        ConnectorSandboxEvidenceContractStatus
        .LOCAL_EVIDENCE_READY
    )
    source_execution_allowed: bool = False
    payload_body_allowed: bool = False
    raw_response_allowed: bool = False
    secret_material_allowed: bool = False
    credential_resolution_allowed: bool = False
    dispatcher_invocation_allowed: bool = False
    network_access_allowed: bool = False
    persistence_allowed: bool = False
    background_task_allowed: bool = False
    external_export_execution_allowed: bool = False
    route_exposure_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        for name in (
            "evidence_contract_id",
            "workflow_id",
            "bundle_type_reference",
            "output_mode_reference",
        ):
            _validate_reference(name, getattr(self, name))

        _validate_reference_tuple(
            "source_type_references",
            self.source_type_references,
        )

        if self.workflow_id != _WORKFLOW_ID:
            raise ValueError(
                "evidence contract must reference the governed workflow."
            )

        if self.source_type_references != (
            "ConnectorSandboxReadWorkflowResult",
            "ConnectorSandboxReadFaultResult",
        ):
            raise ValueError(
                "evidence source types must remain fixed."
            )

        if not isinstance(
            self.status,
            ConnectorSandboxEvidenceContractStatus,
        ):
            raise TypeError(
                "status must be "
                "ConnectorSandboxEvidenceContractStatus."
            )

        for name in _REQUIRED_TRUE_CONTRACT_FLAGS:
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


@dataclass(frozen=True, slots=True)
class ConnectorSandboxEvidenceAssessment:
    evidence_contract_id: str
    workflow_id: str
    status: ConnectorSandboxEvidenceContractStatus
    contract_valid: bool
    source_types_valid: bool
    local_evidence_available: bool
    deterministic: bool
    reference_only: bool
    non_persistent_by_default: bool
    export_safe_references_only: bool
    source_execution_allowed: bool
    payload_body_allowed: bool
    raw_response_allowed: bool
    secret_material_allowed: bool
    credential_resolution_allowed: bool
    dispatcher_invocation_allowed: bool
    network_access_allowed: bool
    persistence_allowed: bool
    background_task_allowed: bool
    external_export_execution_allowed: bool
    route_exposure_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConnectorSandboxEvidenceRequest:
    evidence_id: str
    evidence_contract_id: str
    source_result: (
        ConnectorSandboxReadWorkflowResult
        | ConnectorSandboxReadFaultResult
    )

    def __post_init__(self) -> None:
        _validate_reference("evidence_id", self.evidence_id)
        _validate_reference(
            "evidence_contract_id",
            self.evidence_contract_id,
        )

        if not isinstance(
            self.source_result,
            (
                ConnectorSandboxReadWorkflowResult,
                ConnectorSandboxReadFaultResult,
            ),
        ):
            raise TypeError(
                "source_result must be an R5 workflow result "
                "or R6 fault result."
            )


@dataclass(frozen=True, slots=True)
class ConnectorSandboxEvidenceBundle:
    evidence_id: str
    evidence_contract_id: str
    source_kind: ConnectorSandboxEvidenceSourceKind
    source_request_reference: str
    workflow_id: str
    plan_id_reference: str
    fault_profile_id_reference: str
    source_status_reference: str
    reason_code: str
    result_reference: str
    result_type_reference: str
    source_reference: str
    metadata_references: tuple[str, ...]
    contract_validation_state_reference: str
    request_validation_state_reference: str
    workflow_validation_state_reference: str
    unsafe_flag_projection: tuple[str, ...]
    status: ConnectorSandboxEvidenceBundleStatus
    evidence_captured: bool
    deterministic: bool = True
    immutable: bool = True
    reference_only: bool = True
    local_only: bool = True
    non_persistent: bool = True
    export_safe: bool = True
    source_executed: bool = False
    payload_body_included: bool = False
    raw_response_included: bool = False
    secret_material_included: bool = False
    credentials_resolved: bool = False
    dispatcher_invoked: bool = False
    network_accessed: bool = False
    bundle_persisted: bool = False
    background_task_created: bool = False
    external_export_executed: bool = False
    route_exposed: bool = False
    runtime_used: bool = False
    production_used: bool = False

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "evidence_contract_id",
            "source_request_reference",
            "workflow_id",
            "plan_id_reference",
            "fault_profile_id_reference",
            "source_status_reference",
            "reason_code",
            "result_reference",
            "result_type_reference",
            "source_reference",
            "contract_validation_state_reference",
            "request_validation_state_reference",
            "workflow_validation_state_reference",
        ):
            _validate_reference(name, getattr(self, name))

        _validate_reference_tuple(
            "metadata_references",
            self.metadata_references,
        )
        _validate_reference_tuple(
            "unsafe_flag_projection",
            self.unsafe_flag_projection,
        )

        if not isinstance(
            self.source_kind,
            ConnectorSandboxEvidenceSourceKind,
        ):
            raise TypeError(
                "source_kind must be "
                "ConnectorSandboxEvidenceSourceKind."
            )

        if not isinstance(
            self.status,
            ConnectorSandboxEvidenceBundleStatus,
        ):
            raise TypeError(
                "status must be "
                "ConnectorSandboxEvidenceBundleStatus."
            )

        for name in (
            "deterministic",
            "immutable",
            "reference_only",
            "local_only",
            "non_persistent",
            "export_safe",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_BUNDLE_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


_DECLARED_CONTRACT: Final[ConnectorSandboxEvidenceContract] = (
    ConnectorSandboxEvidenceContract(
        evidence_contract_id=_EVIDENCE_CONTRACT_ID,
        workflow_id=_WORKFLOW_ID,
        source_type_references=(
            "ConnectorSandboxReadWorkflowResult",
            "ConnectorSandboxReadFaultResult",
        ),
        bundle_type_reference=(
            "ConnectorSandboxEvidenceBundle"
        ),
        output_mode_reference=(
            "immutable_reference_only_local_evidence"
        ),
    )
)

CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS = MappingProxyType(
    {
        _DECLARED_CONTRACT.evidence_contract_id: (
            _DECLARED_CONTRACT
        )
    }
)

SUPPORTED_CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS = tuple(
    CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS
)


def list_connector_sandbox_evidence_contracts(
) -> tuple[ConnectorSandboxEvidenceContract, ...]:
    return tuple(
        CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS.values()
    )


def get_connector_sandbox_evidence_contract(
    evidence_contract_id: str,
) -> ConnectorSandboxEvidenceContract:
    normalized = (
        normalize_connector_sandbox_evidence_contract_id(
            evidence_contract_id
        )
    )

    try:
        return CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS[
            normalized
        ]
    except KeyError as exc:
        raise KeyError(
            f"unknown sandbox evidence contract: {normalized}"
        ) from exc


def _contract_validation_issues(
    contract: ConnectorSandboxEvidenceContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    if not isinstance(
        contract,
        ConnectorSandboxEvidenceContract,
    ):
        return ("invalid_evidence_contract_type",)

    if contract.workflow_id != _WORKFLOW_ID:
        issues.append("workflow_reference_mismatch")

    if contract.source_type_references != (
        "ConnectorSandboxReadWorkflowResult",
        "ConnectorSandboxReadFaultResult",
    ):
        issues.append("source_type_reference_mismatch")

    if contract.status is not (
        ConnectorSandboxEvidenceContractStatus
        .LOCAL_EVIDENCE_READY
    ):
        issues.append("evidence_contract_not_ready")

    for name in _REQUIRED_TRUE_CONTRACT_FLAGS:
        if getattr(contract, name) is not True:
            issues.append(f"{name}_required")

    for name in _UNSAFE_CONTRACT_FLAGS:
        if getattr(contract, name) is not False:
            issues.append(f"{name}_must_remain_disabled")

    return tuple(issues)


def validate_connector_sandbox_evidence_contracts(
    contracts: Iterable[ConnectorSandboxEvidenceContract],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, contract in enumerate(contracts):
        if not isinstance(
            contract,
            ConnectorSandboxEvidenceContract,
        ):
            issues.append(
                f"contract_{index}:invalid_evidence_contract_type"
            )
            continue

        if contract.evidence_contract_id in seen_ids:
            issues.append(
                f"{contract.evidence_contract_id}:duplicate_contract_id"
            )

        seen_ids.add(contract.evidence_contract_id)

        for issue in _contract_validation_issues(contract):
            issues.append(
                f"{contract.evidence_contract_id}:{issue}"
            )

    if not seen_ids:
        issues.append("no_evidence_contract_declared")

    return tuple(issues)


def validate_connector_sandbox_evidence_registry(
) -> tuple[str, ...]:
    issues = list(
        validate_connector_sandbox_evidence_contracts(
            list_connector_sandbox_evidence_contracts()
        )
    )

    if tuple(
        CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS
    ) != SUPPORTED_CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS:
        issues.append("supported_contract_order_mismatch")

    for key, contract in (
        CONNECTOR_SANDBOX_EVIDENCE_CONTRACTS.items()
    ):
        if key != contract.evidence_contract_id:
            issues.append(f"{key}:registry_key_mismatch")

    return tuple(issues)


def assess_connector_sandbox_evidence_contract(
    evidence_contract_id: str,
) -> ConnectorSandboxEvidenceAssessment:
    contract = get_connector_sandbox_evidence_contract(
        evidence_contract_id
    )
    issues = _contract_validation_issues(contract)
    valid = not issues

    blockers = [
        "source_execution_disabled",
        "payload_body_disabled",
        "raw_response_disabled",
        "secret_material_disabled",
        "credential_resolution_disabled",
        "dispatcher_invocation_disabled",
        "network_access_disabled",
        "persistence_disabled",
        "background_tasks_disabled",
        "external_export_execution_disabled",
        "route_exposure_disabled",
        "runtime_disabled",
        "production_disabled",
    ]
    blockers.extend(issues)

    return ConnectorSandboxEvidenceAssessment(
        evidence_contract_id=contract.evidence_contract_id,
        workflow_id=contract.workflow_id,
        status=(
            ConnectorSandboxEvidenceContractStatus
            .LOCAL_EVIDENCE_READY
            if valid
            else ConnectorSandboxEvidenceContractStatus.BLOCKED
        ),
        contract_valid=valid,
        source_types_valid=(
            contract.source_type_references
            == (
                "ConnectorSandboxReadWorkflowResult",
                "ConnectorSandboxReadFaultResult",
            )
        ),
        local_evidence_available=valid,
        deterministic=contract.deterministic,
        reference_only=contract.reference_only,
        non_persistent_by_default=(
            contract.non_persistent_by_default
        ),
        export_safe_references_only=(
            contract.export_safe_references_only
        ),
        source_execution_allowed=(
            contract.source_execution_allowed
        ),
        payload_body_allowed=contract.payload_body_allowed,
        raw_response_allowed=contract.raw_response_allowed,
        secret_material_allowed=contract.secret_material_allowed,
        credential_resolution_allowed=(
            contract.credential_resolution_allowed
        ),
        dispatcher_invocation_allowed=(
            contract.dispatcher_invocation_allowed
        ),
        network_access_allowed=contract.network_access_allowed,
        persistence_allowed=contract.persistence_allowed,
        background_task_allowed=contract.background_task_allowed,
        external_export_execution_allowed=(
            contract.external_export_execution_allowed
        ),
        route_exposure_allowed=contract.route_exposure_allowed,
        runtime_enabled=contract.runtime_enabled,
        production_allowed=contract.production_allowed,
        blocker_codes=tuple(blockers),
    )


_WORKFLOW_UNSAFE_FIELDS: Final[tuple[str, ...]] = (
    "real_operation_executed",
    "payload_body_used",
    "secret_accessed",
    "credentials_resolved",
    "dispatcher_invoked",
    "base_transport_invoked",
    "external_http_used",
    "socket_used",
    "payload_persisted",
    "background_task_created",
    "route_exposed",
    "runtime_used",
    "production_used",
)

_FAULT_UNSAFE_FIELDS: Final[tuple[str, ...]] = (
    "real_timeout_waited",
    "retry_executed",
    "automatic_retry_executed",
    "background_retry_created",
    "network_attempted",
    "secret_resolved",
    "dispatcher_invoked",
    "workflow_executed",
    "payload_body_used",
    "payload_persisted",
    "route_exposed",
    "runtime_used",
    "production_used",
)

_CAPTURED_FAULT_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "synthetic_timeout",
        "synthetic_transport_unavailable",
        "synthetic_authorization_denied",
        "synthetic_secret_reference_unavailable",
        "synthetic_plan_rejected",
        "synthetic_operator_approval_missing",
        "synthetic_security_review_missing",
        "synthetic_malformed_reference",
        "safe_refusal",
    }
)


def _status_reference(value: object) -> str:
    candidate = getattr(value, "value", value)

    if not isinstance(candidate, str):
        return "unknown_source_status_reference"

    try:
        return _validate_reference(
            "source_status_reference",
            candidate,
        )
    except (TypeError, ValueError):
        return "unknown_source_status_reference"


def _safe_reference(
    name: str,
    value: object,
    fallback: str,
) -> str:
    try:
        return _validate_reference(name, value)
    except (TypeError, ValueError):
        return fallback


def _safe_reference_tuple(
    name: str,
    value: object,
) -> tuple[str, ...]:
    try:
        return _validate_reference_tuple(name, value)
    except (TypeError, ValueError):
        return ()


def _unsafe_projection(
    source_result: (
        ConnectorSandboxReadWorkflowResult
        | ConnectorSandboxReadFaultResult
    ),
) -> tuple[str, ...]:
    field_names = (
        _WORKFLOW_UNSAFE_FIELDS
        if isinstance(
            source_result,
            ConnectorSandboxReadWorkflowResult,
        )
        else _FAULT_UNSAFE_FIELDS
    )

    return tuple(
        (
            f"{field_name}_true_reference"
            if getattr(source_result, field_name) is True
            else f"{field_name}_false_reference"
        )
        for field_name in field_names
    )


def _enabled_unsafe_fields(
    source_result: (
        ConnectorSandboxReadWorkflowResult
        | ConnectorSandboxReadFaultResult
    ),
) -> tuple[str, ...]:
    field_names = (
        _WORKFLOW_UNSAFE_FIELDS
        if isinstance(
            source_result,
            ConnectorSandboxReadWorkflowResult,
        )
        else _FAULT_UNSAFE_FIELDS
    )

    return tuple(
        field_name
        for field_name in field_names
        if getattr(source_result, field_name) is not False
    )


def _workflow_result_is_valid(
    result: ConnectorSandboxReadWorkflowResult,
) -> bool:
    return (
        _status_reference(result.status)
        == "synthetic_read_completed"
        and result.workflow_id == _WORKFLOW_ID
        and result.contract_validated is True
        and result.request_validated is True
        and result.reference_graph_validated is True
        and result.fake_transport_validated is True
        and result.synthetic_result_completed is True
        and not _enabled_unsafe_fields(result)
        and _safe_reference(
            "synthetic_resource_reference",
            result.synthetic_resource_reference,
            "invalid_reference",
        )
        != "invalid_reference"
        and _safe_reference(
            "synthetic_resource_type_reference",
            result.synthetic_resource_type_reference,
            "invalid_reference",
        )
        != "invalid_reference"
        and _safe_reference(
            "synthetic_source_reference",
            result.synthetic_source_reference,
            "invalid_reference",
        )
        != "invalid_reference"
        and bool(
            _safe_reference_tuple(
                "synthetic_metadata_references",
                result.synthetic_metadata_references,
            )
        )
    )


def _fault_result_is_valid(
    result: ConnectorSandboxReadFaultResult,
) -> bool:
    return (
        _status_reference(result.status)
        in _CAPTURED_FAULT_STATUSES
        and result.workflow_id == _WORKFLOW_ID
        and result.contract_validated is True
        and result.request_validated is True
        and result.workflow_validated is True
        and result.fault_injected is True
        and result.deterministic is True
        and result.immediate_result is True
        and result.safe_refusal is True
        and not _enabled_unsafe_fields(result)
        and _safe_reference(
            "synthetic_fault_reference",
            result.synthetic_fault_reference,
            "invalid_reference",
        )
        != "invalid_reference"
    )


def _source_kind(
    result: (
        ConnectorSandboxReadWorkflowResult
        | ConnectorSandboxReadFaultResult
    ),
) -> ConnectorSandboxEvidenceSourceKind:
    if isinstance(
        result,
        ConnectorSandboxReadWorkflowResult,
    ):
        return (
            ConnectorSandboxEvidenceSourceKind
            .WORKFLOW_RESULT
        )

    return ConnectorSandboxEvidenceSourceKind.FAULT_RESULT


def _validation_reference(
    name: str,
    value: bool,
) -> str:
    suffix = "validated" if value is True else "not_validated"
    return f"{name}_{suffix}_reference"


def build_connector_sandbox_evidence_bundle(
    request: ConnectorSandboxEvidenceRequest,
) -> ConnectorSandboxEvidenceBundle:
    if not isinstance(
        request,
        ConnectorSandboxEvidenceRequest,
    ):
        raise TypeError(
            "request must be ConnectorSandboxEvidenceRequest."
        )

    result = request.source_result
    source_kind = _source_kind(result)
    unsafe_fields = _enabled_unsafe_fields(result)
    projection = _unsafe_projection(result)

    try:
        assessment = (
            assess_connector_sandbox_evidence_contract(
                request.evidence_contract_id
            )
        )
    except KeyError:
        contract_ready = False
    else:
        contract_ready = (
            assessment.contract_valid is True
            and assessment.source_types_valid is True
            and assessment.local_evidence_available is True
            and assessment.source_execution_allowed is False
            and assessment.network_access_allowed is False
            and assessment.persistence_allowed is False
            and assessment.runtime_enabled is False
            and assessment.production_allowed is False
        )

    if isinstance(
        result,
        ConnectorSandboxReadWorkflowResult,
    ):
        source_valid = _workflow_result_is_valid(result)
        plan_id_reference = _safe_reference(
            "plan_id",
            result.plan_id,
            "plan_unavailable_reference",
        )
        fault_profile_id_reference = (
            "fault_profile_not_applicable_reference"
        )
        contract_validated = result.contract_validated
        request_validated = result.request_validated
        workflow_validated = (
            result.reference_graph_validated
        )
        captured_result_reference = _safe_reference(
            "synthetic_resource_reference",
            result.synthetic_resource_reference,
            "result_unavailable_reference",
        )
        captured_result_type = _safe_reference(
            "synthetic_resource_type_reference",
            result.synthetic_resource_type_reference,
            "result_type_unavailable_reference",
        )
        captured_source_reference = _safe_reference(
            "synthetic_source_reference",
            result.synthetic_source_reference,
            "source_unavailable_reference",
        )
        captured_metadata = _safe_reference_tuple(
            "synthetic_metadata_references",
            result.synthetic_metadata_references,
        )
    else:
        source_valid = _fault_result_is_valid(result)
        plan_id_reference = "plan_not_projected_reference"
        fault_profile_id_reference = _safe_reference(
            "fault_profile_id",
            result.fault_profile_id,
            "fault_profile_unavailable_reference",
        )
        contract_validated = result.contract_validated
        request_validated = result.request_validated
        workflow_validated = result.workflow_validated
        captured_result_reference = _safe_reference(
            "synthetic_fault_reference",
            result.synthetic_fault_reference,
            "result_unavailable_reference",
        )
        captured_result_type = (
            "synthetic_sandbox_fault_reference"
        )
        captured_source_reference = (
            "deterministic_local_fault_simulator_reference"
        )
        captured_metadata = ()

    if not contract_ready:
        bundle_status = (
            ConnectorSandboxEvidenceBundleStatus
            .CONTRACT_BLOCKED
        )
        captured = False
    elif unsafe_fields:
        bundle_status = (
            ConnectorSandboxEvidenceBundleStatus
            .UNSAFE_SOURCE_REJECTED
        )
        captured = False
    elif not source_valid:
        bundle_status = (
            ConnectorSandboxEvidenceBundleStatus
            .INVALID_SOURCE_RESULT
        )
        captured = False
    else:
        bundle_status = (
            ConnectorSandboxEvidenceBundleStatus
            .EVIDENCE_CAPTURED
        )
        captured = True

    return ConnectorSandboxEvidenceBundle(
        evidence_id=request.evidence_id,
        evidence_contract_id=request.evidence_contract_id,
        source_kind=source_kind,
        source_request_reference=_safe_reference(
            "source_request_reference",
            result.request_id,
            "source_request_unavailable_reference",
        ),
        workflow_id=_safe_reference(
            "workflow_id",
            result.workflow_id,
            "workflow_unavailable_reference",
        ),
        plan_id_reference=plan_id_reference,
        fault_profile_id_reference=(
            fault_profile_id_reference
        ),
        source_status_reference=_status_reference(
            result.status
        ),
        reason_code=_safe_reference(
            "reason_code",
            result.reason_code,
            "reason_code_unavailable_reference",
        ),
        result_reference=(
            captured_result_reference
            if captured
            else "result_not_captured_reference"
        ),
        result_type_reference=(
            captured_result_type
            if captured
            else "result_type_not_captured_reference"
        ),
        source_reference=(
            captured_source_reference
            if captured
            else "source_not_captured_reference"
        ),
        metadata_references=(
            captured_metadata if captured else ()
        ),
        contract_validation_state_reference=(
            _validation_reference(
                "contract",
                contract_validated,
            )
        ),
        request_validation_state_reference=(
            _validation_reference(
                "request",
                request_validated,
            )
        ),
        workflow_validation_state_reference=(
            _validation_reference(
                "workflow",
                workflow_validated,
            )
        ),
        unsafe_flag_projection=projection,
        status=bundle_status,
        evidence_captured=captured,
    )
