"""Deterministic local fake transport for governed sandbox references.

This module produces synthetic reference metadata only. It never opens a
network connection, invokes a dispatcher, resolves credentials, accepts a
payload body, persists data, creates a worker, or enables runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

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
    ConnectorTransportRequest,
    assess_connector_transport_contract,
    get_connector_transport_contract,
)

__all__ = [
    "CONNECTOR_FAKE_SANDBOX_CONTRACTS",
    "SUPPORTED_CONNECTOR_FAKE_SANDBOX_CONTRACTS",
    "ConnectorDeterministicFakeSandboxTransport",
    "ConnectorFakeSandboxAssessment",
    "ConnectorFakeSandboxContract",
    "ConnectorFakeSandboxMode",
    "ConnectorFakeSandboxRequest",
    "ConnectorFakeSandboxResult",
    "ConnectorFakeSandboxResultStatus",
    "ConnectorFakeSandboxStatus",
    "assess_connector_fake_sandbox_transport",
    "get_connector_fake_sandbox_contract",
    "list_connector_fake_sandbox_contracts",
    "normalize_connector_fake_sandbox_transport_id",
    "validate_connector_fake_sandbox_contracts",
    "validate_connector_fake_sandbox_registry",
]


class ConnectorFakeSandboxMode(StrEnum):
    """Supported fake sandbox transport mode."""

    DETERMINISTIC_LOCAL_REFERENCE_ONLY = (
        "deterministic_local_reference_only_fake_transport"
    )


class ConnectorFakeSandboxStatus(StrEnum):
    """Readiness state of the local fake contract."""

    LOCAL_FAKE_READY = "local_fake_ready"
    BLOCKED = "blocked"


class ConnectorFakeSandboxResultStatus(StrEnum):
    """Safe deterministic fake result outcomes."""

    SYNTHETIC_READ_RESULT = "synthetic_read_result"
    UNKNOWN_FAKE_TRANSPORT = "unknown_fake_transport"
    INVALID_REQUEST = "invalid_request"
    PLAN_MISMATCH = "plan_mismatch"
    CONTRACT_BLOCKED = "contract_blocked"


_PROHIBITED_REFERENCE_MARKERS: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "bearer ",
    "password=",
    "token=",
    "secret=",
    "private_key=",
    "raw_payload=",
)

_SELECTED_FAKE_TRANSPORT_ID: Final[str] = (
    "telecom_ticketing_deterministic_fake_sandbox_transport"
)

_SELECTED_BASE_TRANSPORT_ID: Final[str] = (
    "telecom_ticketing_disabled_no_network_transport"
)

_SELECTED_PILOT_ID: Final[str] = (
    "telecom_ticketing_read_only_sandbox_pilot"
)

_SELECTED_SECRET_MANAGER_CONTRACT_ID: Final[str] = (
    "telecom_operations_customer_vault_secret_manager_contract"
)

_SELECTED_PLAN_ID: Final[str] = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
)

_SELECTED_CONNECTOR_ID: Final[str] = (
    "telecom_ticketing_reference"
)

_REQUEST_TYPE_REFERENCE: Final[str] = (
    "ConnectorTransportRequest"
)

_RESPONSE_TYPE_REFERENCE: Final[str] = (
    "ConnectorFakeSandboxResult"
)

_SYNTHETIC_RESOURCE_REFERENCE: Final[str] = (
    "synthetic_ticket_reference"
)

_SYNTHETIC_RESOURCE_TYPE_REFERENCE: Final[str] = (
    "synthetic_ticket_resource_type_reference"
)

_SYNTHETIC_SOURCE_REFERENCE: Final[str] = (
    "deterministic_local_fixture_v1_reference"
)

_SYNTHETIC_METADATA_REFERENCES: Final[tuple[str, ...]] = (
    "synthetic_ticket_state_open_reference",
    "synthetic_ticket_priority_normal_reference",
    "synthetic_ticket_channel_api_reference",
    "synthetic_ticket_owner_unassigned_reference",
    "synthetic_ticket_created_at_fixed_reference",
)

_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "real_transport_allowed",
    "request_execution_allowed",
    "payload_body_allowed",
    "secret_access_allowed",
    "credentials_resolution_allowed",
    "dispatcher_invocation_allowed",
    "external_http_allowed",
    "socket_access_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "runtime_enabled",
    "production_allowed",
)

_UNSAFE_RESULT_FLAGS: Final[tuple[str, ...]] = (
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


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _validate_reference_text(
    field_name: str,
    value: object,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    if not value:
        raise ValueError(f"{field_name} must not be empty.")

    if value != value.strip():
        raise ValueError(
            f"{field_name} must not contain surrounding whitespace."
        )

    if any(ord(character) < 32 for character in value):
        raise ValueError(
            f"{field_name} must not contain control characters."
        )

    normalized_value = value.casefold()

    for marker in _PROHIBITED_REFERENCE_MARKERS:
        if marker in normalized_value:
            raise ValueError(
                f"{field_name} contains prohibited raw material."
            )


def _validate_reference_sequence(
    field_name: str,
    values: object,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    if not values:
        raise ValueError(f"{field_name} must not be empty.")

    if len(set(values)) != len(values):
        raise ValueError(
            f"{field_name} must not contain duplicate references."
        )

    for value in values:
        _validate_reference_text(
            field_name,
            value,
        )


def _validate_optional_reference_sequence(
    field_name: str,
    values: object,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple.")

    if len(set(values)) != len(values):
        raise ValueError(
            f"{field_name} must not contain duplicate references."
        )

    for value in values:
        _validate_reference_text(
            field_name,
            value,
        )


@dataclass(frozen=True, slots=True)
class ConnectorFakeSandboxContract:
    """Immutable deterministic local fake transport declaration."""

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
    mode: ConnectorFakeSandboxMode
    response_content_mode: str
    fixture_reference: str
    local_only: bool
    sandbox_only: bool
    read_only: bool
    deterministic_output_required: bool
    synthetic_reference_only: bool
    base_transport_must_remain_disabled: bool
    customer_authorization_required: bool
    operator_approval_required: bool
    security_review_required: bool
    status: ConnectorFakeSandboxStatus = (
        ConnectorFakeSandboxStatus.LOCAL_FAKE_READY
    )
    real_transport_allowed: bool = False
    request_execution_allowed: bool = False
    payload_body_allowed: bool = False
    secret_access_allowed: bool = False
    credentials_resolution_allowed: bool = False
    dispatcher_invocation_allowed: bool = False
    external_http_allowed: bool = False
    socket_access_allowed: bool = False
    persistence_allowed: bool = False
    background_task_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
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
            "response_content_mode",
            "fixture_reference",
        ):
            _validate_reference_text(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.mode,
            ConnectorFakeSandboxMode,
        ):
            try:
                normalized_mode = ConnectorFakeSandboxMode(
                    self.mode
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported fake sandbox mode."
                ) from exc

            object.__setattr__(
                self,
                "mode",
                normalized_mode,
            )

        if not isinstance(
            self.status,
            ConnectorFakeSandboxStatus,
        ):
            try:
                normalized_status = ConnectorFakeSandboxStatus(
                    self.status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported fake sandbox status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        if self.mode is not (
            ConnectorFakeSandboxMode
            .DETERMINISTIC_LOCAL_REFERENCE_ONLY
        ):
            raise ValueError(
                "R4 mode must remain deterministic and local."
            )

        if self.status is not (
            ConnectorFakeSandboxStatus.LOCAL_FAKE_READY
        ):
            raise ValueError(
                "R4 contract must remain local-fake ready."
            )

        if self.environment != "sandbox":
            raise ValueError(
                "R4 environment must remain sandbox."
            )

        if self.access_mode != "read":
            raise ValueError(
                "R4 access mode must remain read-only."
            )

        if self.request_type_reference != (
            _REQUEST_TYPE_REFERENCE
        ):
            raise ValueError(
                "Unexpected fake transport request type."
            )

        if self.response_type_reference != (
            _RESPONSE_TYPE_REFERENCE
        ):
            raise ValueError(
                "Unexpected fake transport response type."
            )

        if self.response_content_mode != (
            "synthetic_reference_metadata_only"
        ):
            raise ValueError(
                "R4 output must remain synthetic reference metadata only."
            )

        for field_name in (
            "local_only",
            "sandbox_only",
            "read_only",
            "deterministic_output_required",
            "synthetic_reference_only",
            "base_transport_must_remain_disabled",
            "customer_authorization_required",
            "operator_approval_required",
            "security_review_required",
        ):
            if getattr(self, field_name) is not True:
                raise ValueError(
                    f"{field_name} must remain True in 16E-R4."
                )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R4."
                )


@dataclass(frozen=True, slots=True)
class ConnectorFakeSandboxAssessment:
    """Immutable readiness projection for local fake generation."""

    fake_transport_id: str
    status: ConnectorFakeSandboxStatus
    contract_valid: bool
    reference_graph_valid: bool
    operation_plan_valid: bool
    pilot_valid: bool
    secret_manager_valid: bool
    base_transport_valid: bool
    fake_response_available: bool
    deterministic: bool
    local_only: bool
    synthetic_reference_only: bool
    no_network: bool
    real_transport_allowed: bool
    request_execution_allowed: bool
    payload_body_allowed: bool
    secret_access_allowed: bool
    credentials_resolution_allowed: bool
    dispatcher_invocation_allowed: bool
    external_http_allowed: bool
    socket_access_allowed: bool
    persistence_allowed: bool
    background_task_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_reference_text(
            "fake_transport_id",
            self.fake_transport_id,
        )

        if not isinstance(
            self.status,
            ConnectorFakeSandboxStatus,
        ):
            try:
                normalized_status = ConnectorFakeSandboxStatus(
                    self.status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported fake sandbox assessment status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        boolean_fields = (
            "contract_valid",
            "reference_graph_valid",
            "operation_plan_valid",
            "pilot_valid",
            "secret_manager_valid",
            "base_transport_valid",
            "fake_response_available",
            "deterministic",
            "local_only",
            "synthetic_reference_only",
            "no_network",
            *_UNSAFE_CONTRACT_FLAGS,
        )

        for field_name in boolean_fields:
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        for field_name in (
            "fake_response_available",
            "deterministic",
            "local_only",
            "synthetic_reference_only",
            "no_network",
        ):
            if getattr(self, field_name) is not True:
                raise ValueError(
                    f"{field_name} must remain True in 16E-R4."
                )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R4."
                )

        _validate_reference_sequence(
            "blocker_codes",
            self.blocker_codes,
        )


@dataclass(frozen=True, slots=True)
class ConnectorFakeSandboxRequest:
    """Request wrapper around the existing reference-only transport request."""

    request_id: str
    fake_transport_id: str
    transport_request: ConnectorTransportRequest

    def __post_init__(self) -> None:
        _validate_reference_text(
            "request_id",
            self.request_id,
        )

        _validate_reference_text(
            "fake_transport_id",
            self.fake_transport_id,
        )

        if not isinstance(
            self.transport_request,
            ConnectorTransportRequest,
        ):
            raise TypeError(
                "transport_request must be ConnectorTransportRequest."
            )

        if (
            self.transport_request
            .dispatch_request
            .simulation_mode
            is not True
        ):
            raise ValueError(
                "R4 accepts simulation-mode requests only."
            )


@dataclass(frozen=True, slots=True)
class ConnectorFakeSandboxResult:
    """Synthetic reference-only result with no real transport execution."""

    request_id: str
    fake_transport_id: str
    base_transport_id: str
    plan_id: str
    status: ConnectorFakeSandboxResultStatus
    reason_code: str
    reason: str
    contract_validated: bool
    request_validated: bool
    operation_plan_validated: bool
    pilot_validated: bool
    secret_manager_validated: bool
    base_transport_validated: bool
    synthetic_result_generated: bool
    synthetic_resource_reference: str
    synthetic_resource_type_reference: str
    synthetic_source_reference: str
    synthetic_metadata_references: tuple[str, ...]
    real_transport_attempted: bool = False
    dispatch_attempted: bool = False
    operation_executed: bool = False
    payload_body_used: bool = False
    secret_accessed: bool = False
    credentials_resolved: bool = False
    external_http_used: bool = False
    socket_used: bool = False
    payload_persisted: bool = False
    background_task_created: bool = False
    runtime_used: bool = False
    production_used: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "fake_transport_id",
            "base_transport_id",
            "plan_id",
            "reason_code",
            "reason",
            "synthetic_resource_reference",
            "synthetic_resource_type_reference",
            "synthetic_source_reference",
        ):
            _validate_reference_text(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.status,
            ConnectorFakeSandboxResultStatus,
        ):
            try:
                normalized_status = (
                    ConnectorFakeSandboxResultStatus(
                        self.status
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported fake sandbox result status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        for field_name in (
            "contract_validated",
            "request_validated",
            "operation_plan_validated",
            "pilot_validated",
            "secret_manager_validated",
            "base_transport_validated",
            "synthetic_result_generated",
            *_UNSAFE_RESULT_FLAGS,
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        _validate_optional_reference_sequence(
            "synthetic_metadata_references",
            self.synthetic_metadata_references,
        )

        if self.status is (
            ConnectorFakeSandboxResultStatus
            .SYNTHETIC_READ_RESULT
        ):
            if self.synthetic_result_generated is not True:
                raise ValueError(
                    "Synthetic success must mark result generated."
                )

            if not self.synthetic_metadata_references:
                raise ValueError(
                    "Synthetic success requires metadata references."
                )
        else:
            if self.synthetic_result_generated is not False:
                raise ValueError(
                    "Non-success result must not mark synthetic generation."
                )

            if self.synthetic_metadata_references:
                raise ValueError(
                    "Non-success result must not expose synthetic metadata."
                )

        for field_name in _UNSAFE_RESULT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R4."
                )


def normalize_connector_fake_sandbox_transport_id(
    fake_transport_id: str,
) -> str:
    """Normalize a fake sandbox transport identifier."""

    if not isinstance(fake_transport_id, str):
        raise TypeError(
            "fake_transport_id must be a string."
        )

    normalized = fake_transport_id.strip().casefold()

    _validate_reference_text(
        "fake_transport_id",
        normalized,
    )

    return normalized


def _operation_plan_is_default_deny(
    plan: ConnectorOperationPlan,
) -> bool:
    if plan.connector_id != _SELECTED_CONNECTOR_ID:
        return False

    if _enum_value(plan.environment) != "sandbox":
        return False

    if _enum_value(plan.access_mode) != "read":
        return False

    if _enum_value(plan.status) != "planning_only":
        return False

    if not plan.steps:
        return False

    if _enum_value(
        plan.steps[-1].step_kind
    ) != "block_dispatch":
        return False

    for field_name in (
        "action_execution_allowed",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "credentials_resolution_allowed",
    ):
        if getattr(plan, field_name) is not False:
            return False

    for step in plan.steps:
        if step.execution_allowed is not False:
            return False

        if step.external_http_allowed is not False:
            return False

        if step.credentials_resolution_allowed is not False:
            return False

    return True


def _pilot_is_default_deny(
    pilot: ConnectorSandboxPilotContract,
    assessment: ConnectorSandboxPilotAssessment,
) -> bool:
    if pilot.environment != "sandbox":
        return False

    if pilot.access_mode != "read":
        return False

    if pilot.sandbox_only is not True:
        return False

    if pilot.read_only is not True:
        return False

    if assessment.contract_valid is not True:
        return False

    if assessment.reference_graph_valid is not True:
        return False

    for field_name in (
        "credentials_resolved",
        "runtime_enabled",
        "external_http_enabled",
        "dispatch_allowed",
        "production_allowed",
        "action_execution_allowed",
    ):
        if getattr(assessment, field_name) is not False:
            return False

    return True


def _secret_manager_is_default_deny(
    contract: ConnectorSecretManagerContract,
    assessment: ConnectorSecretManagerAssessment,
) -> bool:
    if contract.sandbox_only is not True:
        return False

    if assessment.contract_valid is not True:
        return False

    if assessment.reference_graph_valid is not True:
        return False

    for field_name in (
        "reference_registered",
        "reference_validated",
        "resolution_allowed",
        "credentials_resolved",
        "value_stored",
        "raw_secret_visible",
        "runtime_enabled",
        "production_allowed",
    ):
        if getattr(assessment, field_name) is not False:
            return False

    return True


def _base_transport_is_default_deny(
    contract: ConnectorTransportContract,
    assessment: ConnectorTransportAssessment,
) -> bool:
    if contract.mode is not (
        ConnectorTransportMode.DISABLED_NO_NETWORK_INTERFACE
    ):
        return False

    if contract.status is not (
        ConnectorTransportContractStatus.DISABLED
    ):
        return False

    if contract.environment != "sandbox":
        return False

    if contract.access_mode != "read":
        return False

    if assessment.contract_valid is not True:
        return False

    if assessment.reference_graph_valid is not True:
        return False

    if assessment.no_network is not True:
        return False

    for field_name in (
        "transport_registered",
        "transport_validated",
        "request_execution_allowed",
        "secret_access_allowed",
        "credentials_resolution_allowed",
        "dispatch_allowed",
        "external_http_allowed",
        "socket_access_allowed",
        "persistence_allowed",
        "background_task_allowed",
        "runtime_enabled",
        "production_allowed",
    ):
        if getattr(assessment, field_name) is not False:
            return False

    return True


def _contract_validation_issues(
    contract: ConnectorFakeSandboxContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    try:
        plan = get_connector_operation_plan(
            contract.plan_id
        )
    except KeyError:
        plan = None
        issues.append(
            f"{contract.fake_transport_id}:operation_plan_not_found"
        )

    try:
        pilot = get_connector_sandbox_pilot_contract(
            contract.pilot_id
        )
    except KeyError:
        pilot = None
        pilot_assessment = None
        issues.append(
            f"{contract.fake_transport_id}:sandbox_pilot_not_found"
        )
    else:
        pilot_assessment = assess_connector_sandbox_pilot(
            contract.pilot_id
        )

    try:
        secret_contract = (
            get_connector_secret_manager_contract(
                contract.secret_manager_contract_id
            )
        )
    except KeyError:
        secret_contract = None
        secret_assessment = None
        issues.append(
            f"{contract.fake_transport_id}:"
            "secret_manager_contract_not_found"
        )
    else:
        secret_assessment = (
            assess_connector_secret_manager_contract(
                contract.secret_manager_contract_id
            )
        )

    try:
        base_transport = get_connector_transport_contract(
            contract.base_transport_id
        )
    except KeyError:
        base_transport = None
        base_transport_assessment = None
        issues.append(
            f"{contract.fake_transport_id}:base_transport_not_found"
        )
    else:
        base_transport_assessment = (
            assess_connector_transport_contract(
                contract.base_transport_id
            )
        )

    if plan is not None:
        if plan.connector_id != contract.connector_id:
            issues.append(
                f"{contract.fake_transport_id}:"
                "operation_plan_connector_mismatch"
            )

        if _enum_value(plan.environment) != (
            contract.environment
        ):
            issues.append(
                f"{contract.fake_transport_id}:"
                "operation_plan_environment_mismatch"
            )

        if _enum_value(plan.access_mode) != (
            contract.access_mode
        ):
            issues.append(
                f"{contract.fake_transport_id}:"
                "operation_plan_access_mismatch"
            )

        if not _operation_plan_is_default_deny(plan):
            issues.append(
                f"{contract.fake_transport_id}:"
                "operation_plan_not_default_deny"
            )

    if pilot is not None and pilot_assessment is not None:
        if pilot.selected_plan_id != contract.plan_id:
            issues.append(
                f"{contract.fake_transport_id}:pilot_plan_mismatch"
            )

        if pilot.connector_id != contract.connector_id:
            issues.append(
                f"{contract.fake_transport_id}:"
                "pilot_connector_mismatch"
            )

        if not _pilot_is_default_deny(
            pilot,
            pilot_assessment,
        ):
            issues.append(
                f"{contract.fake_transport_id}:"
                "sandbox_pilot_not_default_deny"
            )

    if (
        secret_contract is not None
        and secret_assessment is not None
    ):
        if secret_contract.pilot_id != contract.pilot_id:
            issues.append(
                f"{contract.fake_transport_id}:"
                "secret_manager_pilot_mismatch"
            )

        if not _secret_manager_is_default_deny(
            secret_contract,
            secret_assessment,
        ):
            issues.append(
                f"{contract.fake_transport_id}:"
                "secret_manager_not_default_deny"
            )

    if (
        base_transport is not None
        and base_transport_assessment is not None
    ):
        if base_transport.pilot_id != contract.pilot_id:
            issues.append(
                f"{contract.fake_transport_id}:"
                "base_transport_pilot_mismatch"
            )

        if base_transport.plan_id != contract.plan_id:
            issues.append(
                f"{contract.fake_transport_id}:"
                "base_transport_plan_mismatch"
            )

        if base_transport.secret_manager_contract_id != (
            contract.secret_manager_contract_id
        ):
            issues.append(
                f"{contract.fake_transport_id}:"
                "base_transport_secret_manager_mismatch"
            )

        if not _base_transport_is_default_deny(
            base_transport,
            base_transport_assessment,
        ):
            issues.append(
                f"{contract.fake_transport_id}:"
                "base_transport_not_default_deny"
            )

    return tuple(issues)


def validate_connector_fake_sandbox_contracts(
    contracts: tuple[ConnectorFakeSandboxContract, ...],
) -> tuple[str, ...]:
    """Validate fake sandbox contracts against governed references."""

    issues: list[str] = []
    seen_ids: set[str] = set()

    for contract in contracts:
        if not isinstance(
            contract,
            ConnectorFakeSandboxContract,
        ):
            issues.append(
                "connector_fake_sandbox_contract_type_invalid"
            )
            continue

        if contract.fake_transport_id in seen_ids:
            issues.append(
                f"{contract.fake_transport_id}:"
                "duplicate_fake_transport_id"
            )

        seen_ids.add(contract.fake_transport_id)

        issues.extend(
            _contract_validation_issues(contract)
        )

    return tuple(issues)


_TELECOM_TICKETING_FAKE_SANDBOX_CONTRACT = (
    ConnectorFakeSandboxContract(
        fake_transport_id=_SELECTED_FAKE_TRANSPORT_ID,
        base_transport_id=_SELECTED_BASE_TRANSPORT_ID,
        pilot_id=_SELECTED_PILOT_ID,
        secret_manager_contract_id=(
            _SELECTED_SECRET_MANAGER_CONTRACT_ID
        ),
        plan_id=_SELECTED_PLAN_ID,
        connector_id=_SELECTED_CONNECTOR_ID,
        environment="sandbox",
        access_mode="read",
        request_type_reference=_REQUEST_TYPE_REFERENCE,
        response_type_reference=_RESPONSE_TYPE_REFERENCE,
        mode=(
            ConnectorFakeSandboxMode
            .DETERMINISTIC_LOCAL_REFERENCE_ONLY
        ),
        response_content_mode=(
            "synthetic_reference_metadata_only"
        ),
        fixture_reference=_SYNTHETIC_SOURCE_REFERENCE,
        local_only=True,
        sandbox_only=True,
        read_only=True,
        deterministic_output_required=True,
        synthetic_reference_only=True,
        base_transport_must_remain_disabled=True,
        customer_authorization_required=True,
        operator_approval_required=True,
        security_review_required=True,
    )
)

_CONNECTOR_FAKE_SANDBOX_CONTRACTS = {
    _TELECOM_TICKETING_FAKE_SANDBOX_CONTRACT.fake_transport_id: (
        _TELECOM_TICKETING_FAKE_SANDBOX_CONTRACT
    ),
}

CONNECTOR_FAKE_SANDBOX_CONTRACTS = MappingProxyType(
    _CONNECTOR_FAKE_SANDBOX_CONTRACTS
)

SUPPORTED_CONNECTOR_FAKE_SANDBOX_CONTRACTS = tuple(
    CONNECTOR_FAKE_SANDBOX_CONTRACTS
)


def list_connector_fake_sandbox_contracts(
) -> tuple[ConnectorFakeSandboxContract, ...]:
    """List immutable local fake transport contracts."""

    return tuple(
        CONNECTOR_FAKE_SANDBOX_CONTRACTS.values()
    )


def get_connector_fake_sandbox_contract(
    fake_transport_id: str,
) -> ConnectorFakeSandboxContract:
    """Return one normalized local fake transport contract."""

    normalized_id = (
        normalize_connector_fake_sandbox_transport_id(
            fake_transport_id
        )
    )

    try:
        return CONNECTOR_FAKE_SANDBOX_CONTRACTS[
            normalized_id
        ]
    except KeyError as exc:
        raise KeyError(
            f"Unknown connector fake sandbox transport: "
            f"{normalized_id}"
        ) from exc


def validate_connector_fake_sandbox_registry(
) -> tuple[str, ...]:
    """Validate the built-in fake sandbox registry."""

    return validate_connector_fake_sandbox_contracts(
        list_connector_fake_sandbox_contracts()
    )


def assess_connector_fake_sandbox_transport(
    fake_transport_id: str,
) -> ConnectorFakeSandboxAssessment:
    """Project local fake readiness without executing a connector."""

    contract = get_connector_fake_sandbox_contract(
        fake_transport_id
    )

    contract_issues = _contract_validation_issues(
        contract
    )

    operation_plan_valid = False
    pilot_valid = False
    secret_manager_valid = False
    base_transport_valid = False

    try:
        plan = get_connector_operation_plan(
            contract.plan_id
        )
    except KeyError:
        plan = None

    if plan is not None:
        operation_plan_valid = (
            _operation_plan_is_default_deny(plan)
        )

    try:
        pilot = get_connector_sandbox_pilot_contract(
            contract.pilot_id
        )
    except KeyError:
        pilot = None

    if pilot is not None:
        pilot_assessment = assess_connector_sandbox_pilot(
            contract.pilot_id
        )

        pilot_valid = _pilot_is_default_deny(
            pilot,
            pilot_assessment,
        )

    try:
        secret_contract = (
            get_connector_secret_manager_contract(
                contract.secret_manager_contract_id
            )
        )
    except KeyError:
        secret_contract = None

    if secret_contract is not None:
        secret_assessment = (
            assess_connector_secret_manager_contract(
                contract.secret_manager_contract_id
            )
        )

        secret_manager_valid = (
            _secret_manager_is_default_deny(
                secret_contract,
                secret_assessment,
            )
        )

    try:
        base_transport = get_connector_transport_contract(
            contract.base_transport_id
        )
    except KeyError:
        base_transport = None

    if base_transport is not None:
        base_transport_assessment = (
            assess_connector_transport_contract(
                contract.base_transport_id
            )
        )

        base_transport_valid = (
            _base_transport_is_default_deny(
                base_transport,
                base_transport_assessment,
            )
        )

    blockers = [
        "real_transport_disabled",
        "request_execution_disabled",
        "payload_body_disabled",
        "secret_access_disabled",
        "credential_resolution_disabled",
        "dispatcher_invocation_disabled",
        "external_http_disabled",
        "socket_access_disabled",
        "persistence_disabled",
        "background_tasks_disabled",
        "runtime_disabled",
        "production_disabled",
    ]

    if contract_issues:
        blockers.insert(
            0,
            "fake_sandbox_contract_invalid",
        )

    return ConnectorFakeSandboxAssessment(
        fake_transport_id=contract.fake_transport_id,
        status=(
            ConnectorFakeSandboxStatus.BLOCKED
            if contract_issues
            else ConnectorFakeSandboxStatus.LOCAL_FAKE_READY
        ),
        contract_valid=not contract_issues,
        reference_graph_valid=not contract_issues,
        operation_plan_valid=operation_plan_valid,
        pilot_valid=pilot_valid,
        secret_manager_valid=secret_manager_valid,
        base_transport_valid=base_transport_valid,
        fake_response_available=True,
        deterministic=True,
        local_only=True,
        synthetic_reference_only=True,
        no_network=True,
        real_transport_allowed=False,
        request_execution_allowed=False,
        payload_body_allowed=False,
        secret_access_allowed=False,
        credentials_resolution_allowed=False,
        dispatcher_invocation_allowed=False,
        external_http_allowed=False,
        socket_access_allowed=False,
        persistence_allowed=False,
        background_task_allowed=False,
        runtime_enabled=False,
        production_allowed=False,
        blocker_codes=tuple(
            dict.fromkeys(blockers)
        ),
    )


def _dispatch_request_metadata_valid(
    request: ConnectorTransportRequest,
) -> bool:
    try:
        _validate_reference_text(
            "transport_request_id",
            request.request_id,
        )

        _validate_reference_text(
            "base_transport_id",
            request.transport_id,
        )
    except (TypeError, ValueError):
        return False

    dispatch_request = request.dispatch_request

    for field_name in (
        "request_id",
        "plan_id",
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
            _validate_reference_text(
                field_name,
                getattr(dispatch_request, field_name),
            )
        except (TypeError, ValueError):
            return False

    return dispatch_request.simulation_mode is True


def _build_result(
    *,
    request: ConnectorFakeSandboxRequest,
    status: ConnectorFakeSandboxResultStatus,
    reason_code: str,
    reason: str,
    contract_validated: bool,
    request_validated: bool,
    operation_plan_validated: bool,
    pilot_validated: bool,
    secret_manager_validated: bool,
    base_transport_validated: bool,
    synthetic_result_generated: bool,
) -> ConnectorFakeSandboxResult:
    return ConnectorFakeSandboxResult(
        request_id=request.request_id,
        fake_transport_id=request.fake_transport_id,
        base_transport_id=request.transport_request.transport_id,
        plan_id=(
            request.transport_request
            .dispatch_request
            .plan_id
        ),
        status=status,
        reason_code=reason_code,
        reason=reason,
        contract_validated=contract_validated,
        request_validated=request_validated,
        operation_plan_validated=operation_plan_validated,
        pilot_validated=pilot_validated,
        secret_manager_validated=secret_manager_validated,
        base_transport_validated=base_transport_validated,
        synthetic_result_generated=synthetic_result_generated,
        synthetic_resource_reference=(
            _SYNTHETIC_RESOURCE_REFERENCE
            if synthetic_result_generated
            else "synthetic_result_unavailable_reference"
        ),
        synthetic_resource_type_reference=(
            _SYNTHETIC_RESOURCE_TYPE_REFERENCE
            if synthetic_result_generated
            else "synthetic_resource_type_unavailable_reference"
        ),
        synthetic_source_reference=(
            _SYNTHETIC_SOURCE_REFERENCE
            if synthetic_result_generated
            else "synthetic_source_unavailable_reference"
        ),
        synthetic_metadata_references=(
            _SYNTHETIC_METADATA_REFERENCES
            if synthetic_result_generated
            else ()
        ),
    )


class ConnectorDeterministicFakeSandboxTransport:
    """Generate one deterministic synthetic read result locally."""

    def simulate(
        self,
        request: ConnectorFakeSandboxRequest,
    ) -> ConnectorFakeSandboxResult:
        """Return synthetic references without real connector execution."""

        if not isinstance(
            request,
            ConnectorFakeSandboxRequest,
        ):
            raise TypeError(
                "request must be ConnectorFakeSandboxRequest."
            )

        try:
            contract = get_connector_fake_sandbox_contract(
                request.fake_transport_id
            )
        except KeyError:
            return _build_result(
                request=request,
                status=(
                    ConnectorFakeSandboxResultStatus
                    .UNKNOWN_FAKE_TRANSPORT
                ),
                reason_code="unknown_fake_transport_reference",
                reason="fake sandbox transport reference is not declared",
                contract_validated=False,
                request_validated=True,
                operation_plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
                base_transport_validated=False,
                synthetic_result_generated=False,
            )

        request_validated = _dispatch_request_metadata_valid(
            request.transport_request
        )

        if (
            request.transport_request.transport_id
            != contract.base_transport_id
        ):
            request_validated = False

        if not request_validated:
            return _build_result(
                request=request,
                status=(
                    ConnectorFakeSandboxResultStatus
                    .INVALID_REQUEST
                ),
                reason_code="invalid_reference_only_fake_request",
                reason="fake sandbox request references are invalid",
                contract_validated=True,
                request_validated=False,
                operation_plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
                base_transport_validated=False,
                synthetic_result_generated=False,
            )

        request_plan_id = (
            request.transport_request
            .dispatch_request
            .plan_id
        )

        if request_plan_id != contract.plan_id:
            return _build_result(
                request=request,
                status=(
                    ConnectorFakeSandboxResultStatus
                    .PLAN_MISMATCH
                ),
                reason_code="fake_transport_plan_reference_mismatch",
                reason="request plan does not match fake transport contract",
                contract_validated=True,
                request_validated=True,
                operation_plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
                base_transport_validated=False,
                synthetic_result_generated=False,
            )

        contract_issues = _contract_validation_issues(
            contract
        )

        if contract_issues:
            return _build_result(
                request=request,
                status=(
                    ConnectorFakeSandboxResultStatus
                    .CONTRACT_BLOCKED
                ),
                reason_code="fake_sandbox_contract_invalid",
                reason="fake sandbox reference graph is invalid",
                contract_validated=False,
                request_validated=True,
                operation_plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
                base_transport_validated=False,
                synthetic_result_generated=False,
            )

        return _build_result(
            request=request,
            status=(
                ConnectorFakeSandboxResultStatus
                .SYNTHETIC_READ_RESULT
            ),
            reason_code="deterministic_synthetic_ticket_reference",
            reason=(
                "deterministic synthetic ticket references "
                "generated locally"
            ),
            contract_validated=True,
            request_validated=True,
            operation_plan_validated=True,
            pilot_validated=True,
            secret_manager_validated=True,
            base_transport_validated=True,
            synthetic_result_generated=True,
        )
