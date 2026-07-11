"""Governed deterministic local sandbox-read workflow.

This module composes the existing planning, pilot, secret-reference,
disabled-transport, and deterministic fake-transport contracts. It invokes
only the R4 local fake simulation and never invokes a real connector,
dispatcher, endpoint, secret manager, runtime, route, or persistence layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.fake_sandbox_transport import (
    ConnectorDeterministicFakeSandboxTransport,
    ConnectorFakeSandboxAssessment,
    ConnectorFakeSandboxContract,
    ConnectorFakeSandboxMode,
    ConnectorFakeSandboxRequest,
    ConnectorFakeSandboxResult,
    ConnectorFakeSandboxResultStatus,
    ConnectorFakeSandboxStatus,
    assess_connector_fake_sandbox_transport,
    get_connector_fake_sandbox_contract,
)
from processual_api.integrations.operation_plans import (
    ConnectorOperationPlan,
    get_connector_operation_plan,
)
from processual_api.integrations.sandbox_pilot import (
    ConnectorSandboxPilotAssessment,
    ConnectorSandboxPilotContract,
    assess_connector_sandbox_pilot,
    get_connector_sandbox_pilot_contract,
)
from processual_api.integrations.secret_manager_contracts import (
    ConnectorSecretManagerAssessment,
    ConnectorSecretManagerContract,
    assess_connector_secret_manager_contract,
    get_connector_secret_manager_contract,
)
from processual_api.integrations.transport_contracts import (
    ConnectorTransportAssessment,
    ConnectorTransportContract,
    ConnectorTransportContractStatus,
    ConnectorTransportMode,
    assess_connector_transport_contract,
    get_connector_transport_contract,
)

__all__ = [
    "CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS",
    "SUPPORTED_CONNECTOR_SANDBOX_READ_WORKFLOWS",
    "ConnectorDeterministicSandboxReadWorkflow",
    "ConnectorSandboxReadWorkflowAssessment",
    "ConnectorSandboxReadWorkflowContract",
    "ConnectorSandboxReadWorkflowMode",
    "ConnectorSandboxReadWorkflowRequest",
    "ConnectorSandboxReadWorkflowResult",
    "ConnectorSandboxReadWorkflowResultStatus",
    "ConnectorSandboxReadWorkflowStatus",
    "assess_connector_sandbox_read_workflow",
    "execute_connector_sandbox_read_workflow",
    "get_connector_sandbox_read_workflow_contract",
    "list_connector_sandbox_read_workflow_contracts",
    "normalize_connector_sandbox_read_workflow_id",
    "validate_connector_sandbox_read_workflow_contracts",
    "validate_connector_sandbox_read_workflow_registry",
]


class ConnectorSandboxReadWorkflowMode(StrEnum):
    GOVERNED_DETERMINISTIC_LOCAL_READ = (
        "governed_deterministic_local_read_happy_path"
    )


class ConnectorSandboxReadWorkflowStatus(StrEnum):
    LOCAL_HAPPY_PATH_READY = "local_happy_path_ready"
    BLOCKED = "blocked"


class ConnectorSandboxReadWorkflowResultStatus(StrEnum):
    SYNTHETIC_READ_COMPLETED = "synthetic_read_completed"
    UNKNOWN_WORKFLOW = "unknown_workflow"
    INVALID_REQUEST = "invalid_request"
    CONTRACT_BLOCKED = "contract_blocked"
    FAKE_TRANSPORT_REJECTED = "fake_transport_rejected"


_WORKFLOW_ID: Final[str] = (
    "telecom_ticketing_deterministic_sandbox_read_workflow"
)
_FAKE_TRANSPORT_ID: Final[str] = (
    "telecom_ticketing_deterministic_fake_sandbox_transport"
)
_BASE_TRANSPORT_ID: Final[str] = (
    "telecom_ticketing_disabled_no_network_transport"
)
_PILOT_ID: Final[str] = (
    "telecom_ticketing_read_only_sandbox_pilot"
)
_SECRET_MANAGER_ID: Final[str] = (
    "telecom_operations_customer_vault_secret_manager_contract"
)
_PLAN_ID: Final[str] = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)
_CONNECTOR_ID: Final[str] = "telecom_ticketing_reference"

_EXPECTED_METADATA: Final[tuple[str, ...]] = (
    "synthetic_ticket_state_open_reference",
    "synthetic_ticket_priority_normal_reference",
    "synthetic_ticket_channel_api_reference",
    "synthetic_ticket_owner_unassigned_reference",
    "synthetic_ticket_created_at_fixed_reference",
)

_REQUIRED_TRUE_FLAGS: Final[tuple[str, ...]] = (
    "local_only",
    "sandbox_only",
    "read_only",
    "deterministic_output_required",
    "synthetic_reference_only",
    "fake_transport_simulation_required",
    "base_transport_must_remain_disabled",
    "customer_authorization_required",
    "operator_approval_required",
    "security_review_required",
)

_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "real_operation_execution_allowed",
    "payload_body_allowed",
    "secret_access_allowed",
    "credentials_resolution_allowed",
    "dispatcher_invocation_allowed",
    "base_transport_invocation_allowed",
    "external_http_allowed",
    "socket_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
)

_UNSAFE_RESULT_FLAGS: Final[tuple[str, ...]] = (
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

_PROHIBITED_MARKERS: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "bearer ",
    "password=",
    "token=",
    "secret=",
    "private_key=",
    "raw_payload=",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _validate_reference(
    field_name: str,
    value: object,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    if not value or value != value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty trimmed reference."
        )

    if any(ord(character) < 32 for character in value):
        raise ValueError(
            f"{field_name} must not contain control characters."
        )

    normalized = value.casefold()

    if any(marker in normalized for marker in _PROHIBITED_MARKERS):
        raise ValueError(
            f"{field_name} contains prohibited raw material."
        )


def _validate_reference_tuple(
    field_name: str,
    values: object,
    *,
    allow_empty: bool,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    if not allow_empty and not values:
        raise ValueError(f"{field_name} must not be empty.")

    if len(values) != len(set(values)):
        raise ValueError(
            f"{field_name} contains duplicate references."
        )

    for value in values:
        _validate_reference(field_name, value)


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadWorkflowContract:
    workflow_id: str
    fake_transport_id: str
    base_transport_id: str
    pilot_id: str
    secret_manager_contract_id: str
    plan_id: str
    connector_id: str
    environment: str
    access_mode: str
    request_type_reference: str
    response_type_reference: str
    mode: ConnectorSandboxReadWorkflowMode
    output_mode: str
    local_only: bool
    sandbox_only: bool
    read_only: bool
    deterministic_output_required: bool
    synthetic_reference_only: bool
    fake_transport_simulation_required: bool
    base_transport_must_remain_disabled: bool
    customer_authorization_required: bool
    operator_approval_required: bool
    security_review_required: bool
    status: ConnectorSandboxReadWorkflowStatus = (
        ConnectorSandboxReadWorkflowStatus.LOCAL_HAPPY_PATH_READY
    )
    real_operation_execution_allowed: bool = False
    payload_body_allowed: bool = False
    secret_access_allowed: bool = False
    credentials_resolution_allowed: bool = False
    dispatcher_invocation_allowed: bool = False
    base_transport_invocation_allowed: bool = False
    external_http_allowed: bool = False
    socket_access_allowed: bool = False
    persistence_allowed: bool = False
    background_task_allowed: bool = False
    route_exposure_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "workflow_id",
            "fake_transport_id",
            "base_transport_id",
            "pilot_id",
            "secret_manager_contract_id",
            "plan_id",
            "connector_id",
            "environment",
            "access_mode",
            "request_type_reference",
            "response_type_reference",
            "output_mode",
        ):
            _validate_reference(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.mode,
            ConnectorSandboxReadWorkflowMode,
        ):
            object.__setattr__(
                self,
                "mode",
                ConnectorSandboxReadWorkflowMode(self.mode),
            )

        if not isinstance(
            self.status,
            ConnectorSandboxReadWorkflowStatus,
        ):
            object.__setattr__(
                self,
                "status",
                ConnectorSandboxReadWorkflowStatus(self.status),
            )

        if self.mode is not (
            ConnectorSandboxReadWorkflowMode
            .GOVERNED_DETERMINISTIC_LOCAL_READ
        ):
            raise ValueError("R5 mode must remain local and deterministic.")

        if self.status is not (
            ConnectorSandboxReadWorkflowStatus
            .LOCAL_HAPPY_PATH_READY
        ):
            raise ValueError("R5 contract must remain local-ready.")

        if self.environment != "sandbox":
            raise ValueError("R5 environment must remain sandbox.")

        if self.access_mode != "read":
            raise ValueError("R5 access must remain read-only.")

        if self.request_type_reference != (
            "ConnectorFakeSandboxRequest"
        ):
            raise ValueError("Unexpected R5 request type reference.")

        if self.response_type_reference != (
            "ConnectorSandboxReadWorkflowResult"
        ):
            raise ValueError("Unexpected R5 response type reference.")

        if self.output_mode != (
            "synthetic_reference_metadata_only"
        ):
            raise ValueError(
                "R5 output must remain reference metadata only."
            )

        for field_name in _REQUIRED_TRUE_FLAGS:
            if getattr(self, field_name) is not True:
                raise ValueError(
                    f"{field_name} must remain True in R5."
                )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in R5."
                )


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadWorkflowAssessment:
    workflow_id: str
    status: ConnectorSandboxReadWorkflowStatus
    contract_valid: bool
    reference_graph_valid: bool
    operation_plan_valid: bool
    pilot_valid: bool
    secret_manager_valid: bool
    base_transport_valid: bool
    fake_transport_valid: bool
    local_happy_path_available: bool
    deterministic: bool
    synthetic_reference_only: bool
    no_network: bool
    real_operation_execution_allowed: bool
    payload_body_allowed: bool
    secret_access_allowed: bool
    credentials_resolution_allowed: bool
    dispatcher_invocation_allowed: bool
    base_transport_invocation_allowed: bool
    external_http_allowed: bool
    socket_access_allowed: bool
    persistence_allowed: bool
    background_task_allowed: bool
    route_exposure_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_reference("workflow_id", self.workflow_id)

        if not isinstance(
            self.status,
            ConnectorSandboxReadWorkflowStatus,
        ):
            object.__setattr__(
                self,
                "status",
                ConnectorSandboxReadWorkflowStatus(self.status),
            )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in R5."
                )

        _validate_reference_tuple(
            "blocker_codes",
            self.blocker_codes,
            allow_empty=False,
        )


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadWorkflowRequest:
    request_id: str
    workflow_id: str
    fake_request: ConnectorFakeSandboxRequest

    def __post_init__(self) -> None:
        _validate_reference("request_id", self.request_id)
        _validate_reference("workflow_id", self.workflow_id)

        if not isinstance(
            self.fake_request,
            ConnectorFakeSandboxRequest,
        ):
            raise TypeError(
                "fake_request must be ConnectorFakeSandboxRequest."
            )

        if (
            self.fake_request
            .transport_request
            .dispatch_request
            .simulation_mode
            is not True
        ):
            raise ValueError("R5 accepts simulation-mode requests only.")


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadWorkflowResult:
    request_id: str
    workflow_id: str
    fake_transport_id: str
    base_transport_id: str
    plan_id: str
    status: ConnectorSandboxReadWorkflowResultStatus
    reason_code: str
    reason: str
    contract_validated: bool
    request_validated: bool
    reference_graph_validated: bool
    fake_transport_validated: bool
    synthetic_result_completed: bool
    fake_result_status_reference: str
    synthetic_resource_reference: str
    synthetic_resource_type_reference: str
    synthetic_source_reference: str
    synthetic_metadata_references: tuple[str, ...]
    real_operation_executed: bool = False
    payload_body_used: bool = False
    secret_accessed: bool = False
    credentials_resolved: bool = False
    dispatcher_invoked: bool = False
    base_transport_invoked: bool = False
    external_http_used: bool = False
    socket_used: bool = False
    payload_persisted: bool = False
    background_task_created: bool = False
    route_exposed: bool = False
    runtime_used: bool = False
    production_used: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "workflow_id",
            "fake_transport_id",
            "base_transport_id",
            "plan_id",
            "reason_code",
            "reason",
            "fake_result_status_reference",
            "synthetic_resource_reference",
            "synthetic_resource_type_reference",
            "synthetic_source_reference",
        ):
            _validate_reference(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.status,
            ConnectorSandboxReadWorkflowResultStatus,
        ):
            object.__setattr__(
                self,
                "status",
                ConnectorSandboxReadWorkflowResultStatus(
                    self.status
                ),
            )

        _validate_reference_tuple(
            "synthetic_metadata_references",
            self.synthetic_metadata_references,
            allow_empty=True,
        )

        succeeded = self.status is (
            ConnectorSandboxReadWorkflowResultStatus
            .SYNTHETIC_READ_COMPLETED
        )

        if succeeded:
            if self.synthetic_result_completed is not True:
                raise ValueError(
                    "Successful workflow must mark completion."
                )

            if self.fake_result_status_reference != (
                "synthetic_read_result"
            ):
                raise ValueError(
                    "Successful workflow requires the R4 result."
                )

            if not self.synthetic_metadata_references:
                raise ValueError(
                    "Successful workflow requires synthetic metadata."
                )
        else:
            if self.synthetic_result_completed is not False:
                raise ValueError(
                    "Rejected workflow must not mark completion."
                )

            if self.synthetic_metadata_references:
                raise ValueError(
                    "Rejected workflow must not expose metadata."
                )

        for field_name in _UNSAFE_RESULT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in R5."
                )


def normalize_connector_sandbox_read_workflow_id(
    workflow_id: str,
) -> str:
    if not isinstance(workflow_id, str):
        raise TypeError("workflow_id must be a string.")

    normalized = workflow_id.strip().casefold()
    _validate_reference("workflow_id", normalized)
    return normalized


def _plan_is_safe(plan: ConnectorOperationPlan) -> bool:
    return (
        plan.connector_id == _CONNECTOR_ID
        and _enum_value(plan.environment) == "sandbox"
        and _enum_value(plan.access_mode) == "read"
        and _enum_value(plan.status) == "planning_only"
        and bool(plan.steps)
        and _enum_value(plan.steps[-1].step_kind)
        == "block_dispatch"
        and not any(
            (
                plan.action_execution_allowed,
                plan.runtime_enabled,
                plan.external_http_enabled,
                plan.production_allowed,
                plan.automatic_activation_allowed,
                plan.credentials_resolution_allowed,
            )
        )
        and all(
            not any(
                (
                    step.execution_allowed,
                    step.external_http_allowed,
                    step.credentials_resolution_allowed,
                )
            )
            for step in plan.steps
        )
    )


def _pilot_is_safe(
    contract: ConnectorSandboxPilotContract,
    assessment: ConnectorSandboxPilotAssessment,
) -> bool:
    return (
        contract.environment == "sandbox"
        and contract.access_mode == "read"
        and contract.sandbox_only is True
        and contract.read_only is True
        and assessment.contract_valid is True
        and assessment.reference_graph_valid is True
        and not any(
            (
                assessment.credentials_resolved,
                assessment.runtime_enabled,
                assessment.external_http_enabled,
                assessment.dispatch_allowed,
                assessment.production_allowed,
                assessment.action_execution_allowed,
            )
        )
    )


def _secret_is_safe(
    contract: ConnectorSecretManagerContract,
    assessment: ConnectorSecretManagerAssessment,
) -> bool:
    return (
        contract.sandbox_only is True
        and assessment.contract_valid is True
        and assessment.reference_graph_valid is True
        and not any(
            (
                assessment.reference_registered,
                assessment.reference_validated,
                assessment.resolution_allowed,
                assessment.credentials_resolved,
                assessment.value_stored,
                assessment.raw_secret_visible,
                assessment.runtime_enabled,
                assessment.production_allowed,
            )
        )
    )


def _base_transport_is_safe(
    contract: ConnectorTransportContract,
    assessment: ConnectorTransportAssessment,
) -> bool:
    return (
        contract.mode
        is ConnectorTransportMode.DISABLED_NO_NETWORK_INTERFACE
        and contract.status
        is ConnectorTransportContractStatus.DISABLED
        and assessment.contract_valid is True
        and assessment.reference_graph_valid is True
        and assessment.no_network is True
        and not any(
            (
                assessment.transport_registered,
                assessment.transport_validated,
                assessment.request_execution_allowed,
                assessment.secret_access_allowed,
                assessment.credentials_resolution_allowed,
                assessment.dispatch_allowed,
                assessment.external_http_allowed,
                assessment.socket_access_allowed,
                assessment.persistence_allowed,
                assessment.background_task_allowed,
                assessment.runtime_enabled,
                assessment.production_allowed,
            )
        )
    )


def _fake_transport_is_safe(
    contract: ConnectorFakeSandboxContract,
    assessment: ConnectorFakeSandboxAssessment,
) -> bool:
    return (
        contract.mode
        is ConnectorFakeSandboxMode
        .DETERMINISTIC_LOCAL_REFERENCE_ONLY
        and contract.status
        is ConnectorFakeSandboxStatus.LOCAL_FAKE_READY
        and contract.local_only is True
        and contract.sandbox_only is True
        and contract.read_only is True
        and assessment.contract_valid is True
        and assessment.reference_graph_valid is True
        and assessment.fake_response_available is True
        and assessment.deterministic is True
        and assessment.local_only is True
        and assessment.synthetic_reference_only is True
        and assessment.no_network is True
        and not any(
            (
                assessment.real_transport_allowed,
                assessment.request_execution_allowed,
                assessment.payload_body_allowed,
                assessment.secret_access_allowed,
                assessment.credentials_resolution_allowed,
                assessment.dispatcher_invocation_allowed,
                assessment.external_http_allowed,
                assessment.socket_access_allowed,
                assessment.persistence_allowed,
                assessment.background_task_allowed,
                assessment.runtime_enabled,
                assessment.production_allowed,
            )
        )
    )


def _graph_state(
    contract: ConnectorSandboxReadWorkflowContract,
) -> tuple[dict[str, bool], tuple[str, ...]]:
    state = {
        "operation_plan_valid": False,
        "pilot_valid": False,
        "secret_manager_valid": False,
        "base_transport_valid": False,
        "fake_transport_valid": False,
    }
    issues: list[str] = []

    try:
        plan = get_connector_operation_plan(contract.plan_id)
    except KeyError:
        issues.append("operation_plan_not_found")
    else:
        state["operation_plan_valid"] = _plan_is_safe(plan)
        if not state["operation_plan_valid"]:
            issues.append("operation_plan_not_safe")

    try:
        pilot = get_connector_sandbox_pilot_contract(
            contract.pilot_id
        )
        pilot_assessment = assess_connector_sandbox_pilot(
            contract.pilot_id
        )
    except KeyError:
        issues.append("sandbox_pilot_not_found")
    else:
        state["pilot_valid"] = (
            pilot.selected_plan_id == contract.plan_id
            and pilot.connector_id == contract.connector_id
            and _pilot_is_safe(pilot, pilot_assessment)
        )
        if not state["pilot_valid"]:
            issues.append("sandbox_pilot_not_safe")

    try:
        secret = get_connector_secret_manager_contract(
            contract.secret_manager_contract_id
        )
        secret_assessment = (
            assess_connector_secret_manager_contract(
                contract.secret_manager_contract_id
            )
        )
    except KeyError:
        issues.append("secret_manager_contract_not_found")
    else:
        state["secret_manager_valid"] = (
            secret.pilot_id == contract.pilot_id
            and _secret_is_safe(secret, secret_assessment)
        )
        if not state["secret_manager_valid"]:
            issues.append("secret_manager_not_safe")

    try:
        base = get_connector_transport_contract(
            contract.base_transport_id
        )
        base_assessment = assess_connector_transport_contract(
            contract.base_transport_id
        )
    except KeyError:
        issues.append("base_transport_not_found")
    else:
        state["base_transport_valid"] = (
            base.pilot_id == contract.pilot_id
            and base.plan_id == contract.plan_id
            and base.secret_manager_contract_id
            == contract.secret_manager_contract_id
            and _base_transport_is_safe(
                base,
                base_assessment,
            )
        )
        if not state["base_transport_valid"]:
            issues.append("base_transport_not_safe")

    try:
        fake = get_connector_fake_sandbox_contract(
            contract.fake_transport_id
        )
        fake_assessment = (
            assess_connector_fake_sandbox_transport(
                contract.fake_transport_id
            )
        )
    except KeyError:
        issues.append("fake_transport_not_found")
    else:
        state["fake_transport_valid"] = (
            fake.base_transport_id == contract.base_transport_id
            and fake.pilot_id == contract.pilot_id
            and fake.secret_manager_contract_id
            == contract.secret_manager_contract_id
            and fake.plan_id == contract.plan_id
            and _fake_transport_is_safe(
                fake,
                fake_assessment,
            )
        )
        if not state["fake_transport_valid"]:
            issues.append("fake_transport_not_safe")

    return state, tuple(issues)


def validate_connector_sandbox_read_workflow_contracts(
    contracts: tuple[ConnectorSandboxReadWorkflowContract, ...],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()

    for contract in contracts:
        if not isinstance(
            contract,
            ConnectorSandboxReadWorkflowContract,
        ):
            issues.append("sandbox_read_workflow_type_invalid")
            continue

        if contract.workflow_id in seen_ids:
            issues.append(
                f"{contract.workflow_id}:duplicate_workflow_id"
            )

        seen_ids.add(contract.workflow_id)

        _, graph_issues = _graph_state(contract)

        issues.extend(
            f"{contract.workflow_id}:{issue}"
            for issue in graph_issues
        )

    return tuple(issues)


_WORKFLOW = ConnectorSandboxReadWorkflowContract(
    workflow_id=_WORKFLOW_ID,
    fake_transport_id=_FAKE_TRANSPORT_ID,
    base_transport_id=_BASE_TRANSPORT_ID,
    pilot_id=_PILOT_ID,
    secret_manager_contract_id=_SECRET_MANAGER_ID,
    plan_id=_PLAN_ID,
    connector_id=_CONNECTOR_ID,
    environment="sandbox",
    access_mode="read",
    request_type_reference="ConnectorFakeSandboxRequest",
    response_type_reference=(
        "ConnectorSandboxReadWorkflowResult"
    ),
    mode=(
        ConnectorSandboxReadWorkflowMode
        .GOVERNED_DETERMINISTIC_LOCAL_READ
    ),
    output_mode="synthetic_reference_metadata_only",
    local_only=True,
    sandbox_only=True,
    read_only=True,
    deterministic_output_required=True,
    synthetic_reference_only=True,
    fake_transport_simulation_required=True,
    base_transport_must_remain_disabled=True,
    customer_authorization_required=True,
    operator_approval_required=True,
    security_review_required=True,
)

CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS = MappingProxyType(
    {_WORKFLOW.workflow_id: _WORKFLOW}
)

SUPPORTED_CONNECTOR_SANDBOX_READ_WORKFLOWS = tuple(
    CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS
)


def list_connector_sandbox_read_workflow_contracts(
) -> tuple[ConnectorSandboxReadWorkflowContract, ...]:
    return tuple(
        CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS.values()
    )


def get_connector_sandbox_read_workflow_contract(
    workflow_id: str,
) -> ConnectorSandboxReadWorkflowContract:
    normalized = normalize_connector_sandbox_read_workflow_id(
        workflow_id
    )

    try:
        return CONNECTOR_SANDBOX_READ_WORKFLOW_CONTRACTS[
            normalized
        ]
    except KeyError as exc:
        raise KeyError(
            f"Unknown sandbox read workflow: {normalized}"
        ) from exc


def validate_connector_sandbox_read_workflow_registry(
) -> tuple[str, ...]:
    return validate_connector_sandbox_read_workflow_contracts(
        list_connector_sandbox_read_workflow_contracts()
    )


def assess_connector_sandbox_read_workflow(
    workflow_id: str,
) -> ConnectorSandboxReadWorkflowAssessment:
    contract = get_connector_sandbox_read_workflow_contract(
        workflow_id
    )
    state, issues = _graph_state(contract)

    blockers = (
        "real_operation_execution_disabled",
        "payload_body_disabled",
        "secret_access_disabled",
        "credential_resolution_disabled",
        "dispatcher_invocation_disabled",
        "base_transport_invocation_disabled",
        "external_http_disabled",
        "socket_access_disabled",
        "persistence_disabled",
        "background_tasks_disabled",
        "route_exposure_disabled",
        "runtime_disabled",
        "production_disabled",
    )

    return ConnectorSandboxReadWorkflowAssessment(
        workflow_id=contract.workflow_id,
        status=(
            ConnectorSandboxReadWorkflowStatus.BLOCKED
            if issues
            else ConnectorSandboxReadWorkflowStatus
            .LOCAL_HAPPY_PATH_READY
        ),
        contract_valid=not issues,
        reference_graph_valid=not issues,
        operation_plan_valid=state["operation_plan_valid"],
        pilot_valid=state["pilot_valid"],
        secret_manager_valid=state["secret_manager_valid"],
        base_transport_valid=state["base_transport_valid"],
        fake_transport_valid=state["fake_transport_valid"],
        local_happy_path_available=not issues,
        deterministic=True,
        synthetic_reference_only=True,
        no_network=True,
        real_operation_execution_allowed=False,
        payload_body_allowed=False,
        secret_access_allowed=False,
        credentials_resolution_allowed=False,
        dispatcher_invocation_allowed=False,
        base_transport_invocation_allowed=False,
        external_http_allowed=False,
        socket_access_allowed=False,
        persistence_allowed=False,
        background_task_allowed=False,
        route_exposure_allowed=False,
        runtime_enabled=False,
        production_allowed=False,
        blocker_codes=blockers,
    )


def _request_is_valid(
    request: ConnectorSandboxReadWorkflowRequest,
    contract: ConnectorSandboxReadWorkflowContract,
) -> bool:
    fake_request = request.fake_request
    transport_request = fake_request.transport_request
    dispatch_request = transport_request.dispatch_request

    if fake_request.fake_transport_id != contract.fake_transport_id:
        return False

    if transport_request.transport_id != contract.base_transport_id:
        return False

    if dispatch_request.plan_id != contract.plan_id:
        return False

    if dispatch_request.simulation_mode is not True:
        return False

    for field_name in (
        "request_id",
        "operation_id",
        "tenant_reference",
        "payload_hash",
        "idempotency_key",
        "requested_at_reference",
        "expires_at_reference",
        "requester_reference",
        "approval_reference",
    ):
        try:
            _validate_reference(
                field_name,
                getattr(dispatch_request, field_name),
            )
        except (TypeError, ValueError):
            return False

    return True


def _fake_result_is_expected(
    result: ConnectorFakeSandboxResult,
) -> bool:
    required_true = (
        "contract_validated",
        "request_validated",
        "operation_plan_validated",
        "pilot_validated",
        "secret_manager_validated",
        "base_transport_validated",
        "synthetic_result_generated",
    )

    fake_unsafe_flags = (
        "real_transport_attempted",
        "dispatch_attempted",
        "operation_executed",
        "payload_body_used",
        "secret_accessed",
        "credentials_resolved",
        "external_http_used",
        "socket_used",
        "payload_persisted",
        "background_task_created",
        "runtime_used",
        "production_used",
    )

    return (
        result.status
        is ConnectorFakeSandboxResultStatus.SYNTHETIC_READ_RESULT
        and all(getattr(result, name) is True for name in required_true)
        and all(
            getattr(result, name) is False
            for name in fake_unsafe_flags
        )
        and result.synthetic_resource_reference
        == "synthetic_ticket_reference"
        and result.synthetic_resource_type_reference
        == "synthetic_ticket_resource_type_reference"
        and result.synthetic_source_reference
        == "deterministic_local_fixture_v1_reference"
        and result.synthetic_metadata_references
        == _EXPECTED_METADATA
    )


def _build_result(
    request: ConnectorSandboxReadWorkflowRequest,
    *,
    status: ConnectorSandboxReadWorkflowResultStatus,
    reason_code: str,
    reason: str,
    contract_validated: bool,
    request_validated: bool,
    graph_validated: bool,
    fake_validated: bool,
    fake_result: ConnectorFakeSandboxResult | None = None,
) -> ConnectorSandboxReadWorkflowResult:
    completed = (
        status
        is ConnectorSandboxReadWorkflowResultStatus
        .SYNTHETIC_READ_COMPLETED
        and fake_result is not None
    )

    return ConnectorSandboxReadWorkflowResult(
        request_id=request.request_id,
        workflow_id=request.workflow_id,
        fake_transport_id=request.fake_request.fake_transport_id,
        base_transport_id=(
            request.fake_request.transport_request.transport_id
        ),
        plan_id=(
            request.fake_request
            .transport_request
            .dispatch_request
            .plan_id
        ),
        status=status,
        reason_code=reason_code,
        reason=reason,
        contract_validated=contract_validated,
        request_validated=request_validated,
        reference_graph_validated=graph_validated,
        fake_transport_validated=fake_validated,
        synthetic_result_completed=completed,
        fake_result_status_reference=(
            str(_enum_value(fake_result.status))
            if fake_result is not None
            else "fake_result_not_generated_reference"
        ),
        synthetic_resource_reference=(
            fake_result.synthetic_resource_reference
            if completed
            else "synthetic_resource_unavailable_reference"
        ),
        synthetic_resource_type_reference=(
            fake_result.synthetic_resource_type_reference
            if completed
            else "synthetic_resource_type_unavailable_reference"
        ),
        synthetic_source_reference=(
            fake_result.synthetic_source_reference
            if completed
            else "synthetic_source_unavailable_reference"
        ),
        synthetic_metadata_references=(
            fake_result.synthetic_metadata_references
            if completed
            else ()
        ),
    )


class ConnectorDeterministicSandboxReadWorkflow:
    def run(
        self,
        request: ConnectorSandboxReadWorkflowRequest,
    ) -> ConnectorSandboxReadWorkflowResult:
        if not isinstance(
            request,
            ConnectorSandboxReadWorkflowRequest,
        ):
            raise TypeError(
                "request must be ConnectorSandboxReadWorkflowRequest."
            )

        try:
            contract = (
                get_connector_sandbox_read_workflow_contract(
                    request.workflow_id
                )
            )
        except KeyError:
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadWorkflowResultStatus
                    .UNKNOWN_WORKFLOW
                ),
                reason_code="unknown_sandbox_read_workflow",
                reason="workflow reference is not declared",
                contract_validated=False,
                request_validated=True,
                graph_validated=False,
                fake_validated=False,
            )

        if not _request_is_valid(request, contract):
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadWorkflowResultStatus
                    .INVALID_REQUEST
                ),
                reason_code="invalid_sandbox_read_workflow_request",
                reason="workflow references are invalid",
                contract_validated=True,
                request_validated=False,
                graph_validated=False,
                fake_validated=False,
            )

        _, graph_issues = _graph_state(contract)

        if graph_issues:
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadWorkflowResultStatus
                    .CONTRACT_BLOCKED
                ),
                reason_code="sandbox_read_workflow_contract_invalid",
                reason="workflow reference graph is invalid",
                contract_validated=False,
                request_validated=True,
                graph_validated=False,
                fake_validated=False,
            )

        fake_result = (
            ConnectorDeterministicFakeSandboxTransport()
            .simulate(request.fake_request)
        )

        if not _fake_result_is_expected(fake_result):
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadWorkflowResultStatus
                    .FAKE_TRANSPORT_REJECTED
                ),
                reason_code="fake_sandbox_transport_rejected",
                reason="fake transport returned an unexpected result",
                contract_validated=True,
                request_validated=True,
                graph_validated=True,
                fake_validated=False,
            )

        return _build_result(
            request,
            status=(
                ConnectorSandboxReadWorkflowResultStatus
                .SYNTHETIC_READ_COMPLETED
            ),
            reason_code="governed_synthetic_ticket_read_completed",
            reason="deterministic synthetic ticket read completed locally",
            contract_validated=True,
            request_validated=True,
            graph_validated=True,
            fake_validated=True,
            fake_result=fake_result,
        )


def execute_connector_sandbox_read_workflow(
    request: ConnectorSandboxReadWorkflowRequest,
) -> ConnectorSandboxReadWorkflowResult:
    return ConnectorDeterministicSandboxReadWorkflow().run(
        request
    )
