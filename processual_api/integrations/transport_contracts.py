"""Disabled no-network transport contracts for governed connector pilots.

The module defines a reference-only transport boundary. It never opens a
network connection, resolves credentials, invokes the mock dispatcher,
persists a payload, creates a worker, or authorizes runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol, runtime_checkable

from processual_api.integrations.mock_dispatcher import (
    ConnectorDispatchRequest,
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

__all__ = [
    "CONNECTOR_TRANSPORT_CONTRACTS",
    "SUPPORTED_CONNECTOR_TRANSPORT_CONTRACTS",
    "ConnectorNoNetworkTransport",
    "ConnectorTransport",
    "ConnectorTransportAssessment",
    "ConnectorTransportContract",
    "ConnectorTransportContractStatus",
    "ConnectorTransportMode",
    "ConnectorTransportRequest",
    "ConnectorTransportResult",
    "ConnectorTransportResultStatus",
    "assess_connector_transport_contract",
    "get_connector_transport_contract",
    "list_connector_transport_contracts",
    "normalize_connector_transport_id",
    "validate_connector_transport_contracts",
    "validate_connector_transport_registry",
]


class ConnectorTransportMode(StrEnum):
    """Transport implementations supported by the R3 boundary."""

    DISABLED_NO_NETWORK_INTERFACE = (
        "disabled_no_network_interface"
    )


class ConnectorTransportContractStatus(StrEnum):
    """Lifecycle state of the declared transport contract."""

    DISABLED = "disabled"
    BLOCKED = "blocked"


class ConnectorTransportResultStatus(StrEnum):
    """Safe outcomes returned without attempting transport."""

    BLOCKED = "blocked"
    UNKNOWN_TRANSPORT = "unknown_transport"
    PLAN_MISMATCH = "plan_mismatch"
    INVALID_REQUEST = "invalid_request"


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

_SELECTED_TRANSPORT_ID: Final[str] = (
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
    "ConnectorDispatchRequest"
)

_RESPONSE_TYPE_REFERENCE: Final[str] = (
    "ConnectorTransportResult"
)

_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
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
)

_UNSAFE_RESULT_FLAGS: Final[tuple[str, ...]] = (
    "transport_attempted",
    "dispatch_attempted",
    "operation_executed",
    "secret_accessed",
    "credentials_resolved",
    "external_http_used",
    "socket_used",
    "payload_persisted",
    "background_task_created",
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
            f"{field_name} must not contain duplicate values."
        )

    for value in values:
        _validate_reference_text(
            field_name,
            value,
        )


@dataclass(frozen=True, slots=True)
class ConnectorTransportContract:
    """Immutable declaration of a disabled transport boundary."""

    transport_id: str
    pilot_id: str
    secret_manager_contract_id: str
    plan_id: str
    connector_id: str
    environment: str
    access_mode: str
    request_type_reference: str
    response_type_reference: str
    mode: ConnectorTransportMode
    sandbox_only: bool
    read_only: bool
    reference_only_request_required: bool
    deterministic_blocking_required: bool
    customer_authorization_required: bool
    operator_approval_required: bool
    security_review_required: bool
    status: ConnectorTransportContractStatus = (
        ConnectorTransportContractStatus.DISABLED
    )
    transport_registered: bool = False
    transport_validated: bool = False
    request_execution_allowed: bool = False
    secret_access_allowed: bool = False
    credentials_resolution_allowed: bool = False
    dispatch_allowed: bool = False
    external_http_allowed: bool = False
    socket_access_allowed: bool = False
    persistence_allowed: bool = False
    background_task_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "transport_id",
            "pilot_id",
            "secret_manager_contract_id",
            "plan_id",
            "connector_id",
            "environment",
            "access_mode",
            "request_type_reference",
            "response_type_reference",
        ):
            _validate_reference_text(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.mode,
            ConnectorTransportMode,
        ):
            try:
                normalized_mode = ConnectorTransportMode(
                    self.mode
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported connector transport mode."
                ) from exc

            object.__setattr__(
                self,
                "mode",
                normalized_mode,
            )

        if not isinstance(
            self.status,
            ConnectorTransportContractStatus,
        ):
            try:
                normalized_status = (
                    ConnectorTransportContractStatus(
                        self.status
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported connector transport status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        if self.mode is not (
            ConnectorTransportMode
            .DISABLED_NO_NETWORK_INTERFACE
        ):
            raise ValueError(
                "R3 transport mode must remain disabled and no-network."
            )

        if self.status is not (
            ConnectorTransportContractStatus.DISABLED
        ):
            raise ValueError(
                "R3 transport contract must remain disabled."
            )

        if self.environment != "sandbox":
            raise ValueError(
                "R3 transport environment must remain sandbox."
            )

        if self.access_mode != "read":
            raise ValueError(
                "R3 transport access must remain read-only."
            )

        if self.request_type_reference != (
            _REQUEST_TYPE_REFERENCE
        ):
            raise ValueError(
                "Unexpected transport request type reference."
            )

        if self.response_type_reference != (
            _RESPONSE_TYPE_REFERENCE
        ):
            raise ValueError(
                "Unexpected transport response type reference."
            )

        for field_name in (
            "sandbox_only",
            "read_only",
            "reference_only_request_required",
            "deterministic_blocking_required",
            "customer_authorization_required",
            "operator_approval_required",
            "security_review_required",
        ):
            if getattr(self, field_name) is not True:
                raise ValueError(
                    f"{field_name} must remain True in 16E-R3."
                )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R3."
                )


@dataclass(frozen=True, slots=True)
class ConnectorTransportAssessment:
    """Immutable readiness projection for a disabled transport."""

    transport_id: str
    status: ConnectorTransportContractStatus
    contract_valid: bool
    reference_graph_valid: bool
    plan_valid: bool
    pilot_valid: bool
    secret_manager_valid: bool
    interface_declared: bool
    deterministic_blocking: bool
    no_network: bool
    transport_registered: bool
    transport_validated: bool
    request_execution_allowed: bool
    secret_access_allowed: bool
    credentials_resolution_allowed: bool
    dispatch_allowed: bool
    external_http_allowed: bool
    socket_access_allowed: bool
    persistence_allowed: bool
    background_task_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_reference_text(
            "transport_id",
            self.transport_id,
        )

        if not isinstance(
            self.status,
            ConnectorTransportContractStatus,
        ):
            try:
                normalized_status = (
                    ConnectorTransportContractStatus(
                        self.status
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported transport assessment status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        boolean_fields = (
            "contract_valid",
            "reference_graph_valid",
            "plan_valid",
            "pilot_valid",
            "secret_manager_valid",
            "interface_declared",
            "deterministic_blocking",
            "no_network",
            *_UNSAFE_CONTRACT_FLAGS,
        )

        for field_name in boolean_fields:
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        for field_name in (
            "interface_declared",
            "deterministic_blocking",
            "no_network",
        ):
            if getattr(self, field_name) is not True:
                raise ValueError(
                    f"{field_name} must remain True in 16E-R3."
                )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R3."
                )

        _validate_reference_sequence(
            "blocker_codes",
            self.blocker_codes,
        )


@dataclass(frozen=True, slots=True)
class ConnectorTransportRequest:
    """Reference-only request accepted by the disabled transport."""

    request_id: str
    transport_id: str
    dispatch_request: ConnectorDispatchRequest

    def __post_init__(self) -> None:
        _validate_reference_text(
            "request_id",
            self.request_id,
        )

        _validate_reference_text(
            "transport_id",
            self.transport_id,
        )

        if not isinstance(
            self.dispatch_request,
            ConnectorDispatchRequest,
        ):
            raise TypeError(
                "dispatch_request must be ConnectorDispatchRequest."
            )

        if self.dispatch_request.simulation_mode is not True:
            raise ValueError(
                "R3 accepts simulation-mode requests only."
            )


@dataclass(frozen=True, slots=True)
class ConnectorTransportResult:
    """Safe result returned without attempting network transport."""

    request_id: str
    transport_id: str
    plan_id: str
    status: ConnectorTransportResultStatus
    reason_code: str
    reason: str
    contract_validated: bool
    request_validated: bool
    plan_validated: bool
    pilot_validated: bool
    secret_manager_validated: bool
    transport_attempted: bool = False
    dispatch_attempted: bool = False
    operation_executed: bool = False
    secret_accessed: bool = False
    credentials_resolved: bool = False
    external_http_used: bool = False
    socket_used: bool = False
    payload_persisted: bool = False
    background_task_created: bool = False
    production_used: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "transport_id",
            "plan_id",
            "reason_code",
            "reason",
        ):
            _validate_reference_text(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.status,
            ConnectorTransportResultStatus,
        ):
            try:
                normalized_status = (
                    ConnectorTransportResultStatus(
                        self.status
                    )
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported transport result status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        for field_name in (
            "contract_validated",
            "request_validated",
            "plan_validated",
            "pilot_validated",
            "secret_manager_validated",
            *_UNSAFE_RESULT_FLAGS,
        ):
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        for field_name in _UNSAFE_RESULT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R3."
                )


@runtime_checkable
class ConnectorTransport(Protocol):
    """Minimal transport protocol for later reviewed implementations."""

    def transmit(
        self,
        request: ConnectorTransportRequest,
    ) -> ConnectorTransportResult:
        """Return a transport result without exposing implementation data."""

        ...


def normalize_connector_transport_id(
    transport_id: str,
) -> str:
    """Normalize a transport identifier."""

    if not isinstance(transport_id, str):
        raise TypeError(
            "transport_id must be a string."
        )

    normalized = transport_id.strip().casefold()

    _validate_reference_text(
        "transport_id",
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


def _contract_validation_issues(
    contract: ConnectorTransportContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    try:
        plan = get_connector_operation_plan(
            contract.plan_id
        )
    except KeyError:
        plan = None
        issues.append(
            f"{contract.transport_id}:operation_plan_not_found"
        )

    try:
        pilot = get_connector_sandbox_pilot_contract(
            contract.pilot_id
        )
    except KeyError:
        pilot = None
        pilot_assessment = None
        issues.append(
            f"{contract.transport_id}:sandbox_pilot_not_found"
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
            f"{contract.transport_id}:"
            "secret_manager_contract_not_found"
        )
    else:
        secret_assessment = (
            assess_connector_secret_manager_contract(
                contract.secret_manager_contract_id
            )
        )

    if plan is not None:
        if plan.plan_id != contract.plan_id:
            issues.append(
                f"{contract.transport_id}:plan_id_mismatch"
            )

        if plan.connector_id != contract.connector_id:
            issues.append(
                f"{contract.transport_id}:connector_id_mismatch"
            )

        if _enum_value(plan.environment) != (
            contract.environment
        ):
            issues.append(
                f"{contract.transport_id}:environment_mismatch"
            )

        if _enum_value(plan.access_mode) != (
            contract.access_mode
        ):
            issues.append(
                f"{contract.transport_id}:access_mode_mismatch"
            )

        if not _operation_plan_is_default_deny(plan):
            issues.append(
                f"{contract.transport_id}:"
                "operation_plan_not_default_deny"
            )

    if pilot is not None and pilot_assessment is not None:
        if pilot.selected_plan_id != contract.plan_id:
            issues.append(
                f"{contract.transport_id}:pilot_plan_mismatch"
            )

        if pilot.connector_id != contract.connector_id:
            issues.append(
                f"{contract.transport_id}:pilot_connector_mismatch"
            )

        if not _pilot_is_default_deny(
            pilot,
            pilot_assessment,
        ):
            issues.append(
                f"{contract.transport_id}:"
                "sandbox_pilot_not_default_deny"
            )

    if (
        secret_contract is not None
        and secret_assessment is not None
    ):
        if secret_contract.pilot_id != contract.pilot_id:
            issues.append(
                f"{contract.transport_id}:"
                "secret_manager_pilot_mismatch"
            )

        if not _secret_manager_is_default_deny(
            secret_contract,
            secret_assessment,
        ):
            issues.append(
                f"{contract.transport_id}:"
                "secret_manager_not_default_deny"
            )

    return tuple(issues)


def validate_connector_transport_contracts(
    contracts: tuple[ConnectorTransportContract, ...],
) -> tuple[str, ...]:
    """Validate transport declarations against governed references."""

    issues: list[str] = []
    seen_ids: set[str] = set()

    for contract in contracts:
        if not isinstance(
            contract,
            ConnectorTransportContract,
        ):
            issues.append(
                "connector_transport_contract_type_invalid"
            )
            continue

        if contract.transport_id in seen_ids:
            issues.append(
                f"{contract.transport_id}:duplicate_transport_id"
            )

        seen_ids.add(contract.transport_id)

        issues.extend(
            _contract_validation_issues(contract)
        )

    return tuple(issues)


_TELECOM_TICKETING_DISABLED_TRANSPORT = (
    ConnectorTransportContract(
        transport_id=_SELECTED_TRANSPORT_ID,
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
            ConnectorTransportMode
            .DISABLED_NO_NETWORK_INTERFACE
        ),
        sandbox_only=True,
        read_only=True,
        reference_only_request_required=True,
        deterministic_blocking_required=True,
        customer_authorization_required=True,
        operator_approval_required=True,
        security_review_required=True,
    )
)

_CONNECTOR_TRANSPORT_CONTRACTS = {
    _TELECOM_TICKETING_DISABLED_TRANSPORT.transport_id: (
        _TELECOM_TICKETING_DISABLED_TRANSPORT
    ),
}

CONNECTOR_TRANSPORT_CONTRACTS = MappingProxyType(
    _CONNECTOR_TRANSPORT_CONTRACTS
)

SUPPORTED_CONNECTOR_TRANSPORT_CONTRACTS = tuple(
    CONNECTOR_TRANSPORT_CONTRACTS
)


def list_connector_transport_contracts(
) -> tuple[ConnectorTransportContract, ...]:
    """List immutable transport declarations."""

    return tuple(
        CONNECTOR_TRANSPORT_CONTRACTS.values()
    )


def get_connector_transport_contract(
    transport_id: str,
) -> ConnectorTransportContract:
    """Return one normalized transport declaration."""

    normalized_id = normalize_connector_transport_id(
        transport_id
    )

    try:
        return CONNECTOR_TRANSPORT_CONTRACTS[
            normalized_id
        ]
    except KeyError as exc:
        raise KeyError(
            f"Unknown connector transport: {normalized_id}"
        ) from exc


def validate_connector_transport_registry(
) -> tuple[str, ...]:
    """Validate the built-in transport registry."""

    return validate_connector_transport_contracts(
        list_connector_transport_contracts()
    )


def assess_connector_transport_contract(
    transport_id: str,
) -> ConnectorTransportAssessment:
    """Project transport readiness without attempting transport."""

    contract = get_connector_transport_contract(
        transport_id
    )

    contract_issues = _contract_validation_issues(
        contract
    )

    plan_valid = False
    pilot_valid = False
    secret_manager_valid = False

    try:
        plan = get_connector_operation_plan(
            contract.plan_id
        )
    except KeyError:
        plan = None

    if plan is not None:
        plan_valid = _operation_plan_is_default_deny(
            plan
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

    blockers = [
        "transport_disabled",
        "transport_registration_pending",
        "transport_validation_pending",
        "request_execution_disabled",
        "secret_access_disabled",
        "credential_resolution_disabled",
        "dispatch_disabled",
        "external_http_disabled",
        "socket_access_disabled",
        "persistence_disabled",
        "background_tasks_disabled",
        "runtime_disabled",
        "production_disabled",
        "sandbox_pilot_pending",
        "secret_manager_reference_pending",
    ]

    if contract_issues:
        blockers.insert(
            0,
            "transport_contract_invalid",
        )

    return ConnectorTransportAssessment(
        transport_id=contract.transport_id,
        status=(
            ConnectorTransportContractStatus.BLOCKED
            if contract_issues
            else ConnectorTransportContractStatus.DISABLED
        ),
        contract_valid=not contract_issues,
        reference_graph_valid=not contract_issues,
        plan_valid=plan_valid,
        pilot_valid=pilot_valid,
        secret_manager_valid=secret_manager_valid,
        interface_declared=True,
        deterministic_blocking=True,
        no_network=True,
        transport_registered=False,
        transport_validated=False,
        request_execution_allowed=False,
        secret_access_allowed=False,
        credentials_resolution_allowed=False,
        dispatch_allowed=False,
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
    request: ConnectorDispatchRequest,
) -> bool:
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
                getattr(request, field_name),
            )
        except (TypeError, ValueError):
            return False

    return request.simulation_mode is True


def _build_result(
    *,
    request: ConnectorTransportRequest,
    status: ConnectorTransportResultStatus,
    reason_code: str,
    reason: str,
    contract_validated: bool,
    request_validated: bool,
    plan_validated: bool,
    pilot_validated: bool,
    secret_manager_validated: bool,
) -> ConnectorTransportResult:
    return ConnectorTransportResult(
        request_id=request.request_id,
        transport_id=request.transport_id,
        plan_id=request.dispatch_request.plan_id,
        status=status,
        reason_code=reason_code,
        reason=reason,
        contract_validated=contract_validated,
        request_validated=request_validated,
        plan_validated=plan_validated,
        pilot_validated=pilot_validated,
        secret_manager_validated=secret_manager_validated,
    )


class ConnectorNoNetworkTransport:
    """Deterministic transport implementation that always blocks."""

    def transmit(
        self,
        request: ConnectorTransportRequest,
    ) -> ConnectorTransportResult:
        """Validate references and return without attempting transport."""

        if not isinstance(
            request,
            ConnectorTransportRequest,
        ):
            raise TypeError(
                "request must be ConnectorTransportRequest."
            )

        try:
            contract = get_connector_transport_contract(
                request.transport_id
            )
        except KeyError:
            return _build_result(
                request=request,
                status=(
                    ConnectorTransportResultStatus
                    .UNKNOWN_TRANSPORT
                ),
                reason_code="unknown_transport_reference",
                reason="transport reference is not declared",
                contract_validated=False,
                request_validated=True,
                plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
            )

        request_validated = _dispatch_request_metadata_valid(
            request.dispatch_request
        )

        if not request_validated:
            return _build_result(
                request=request,
                status=(
                    ConnectorTransportResultStatus
                    .INVALID_REQUEST
                ),
                reason_code="invalid_reference_only_request",
                reason="transport request metadata is invalid",
                contract_validated=False,
                request_validated=False,
                plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
            )

        if request.dispatch_request.plan_id != (
            contract.plan_id
        ):
            return _build_result(
                request=request,
                status=(
                    ConnectorTransportResultStatus
                    .PLAN_MISMATCH
                ),
                reason_code="transport_plan_reference_mismatch",
                reason="request plan does not match transport contract",
                contract_validated=True,
                request_validated=True,
                plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
            )

        contract_issues = _contract_validation_issues(
            contract
        )

        if contract_issues:
            return _build_result(
                request=request,
                status=(
                    ConnectorTransportResultStatus.BLOCKED
                ),
                reason_code="transport_contract_invalid",
                reason="transport contract reference graph is invalid",
                contract_validated=False,
                request_validated=True,
                plan_validated=False,
                pilot_validated=False,
                secret_manager_validated=False,
            )

        return _build_result(
            request=request,
            status=ConnectorTransportResultStatus.BLOCKED,
            reason_code="transport_disabled_no_network",
            reason="transport is disabled and no network was attempted",
            contract_validated=True,
            request_validated=True,
            plan_validated=True,
            pilot_validated=True,
            secret_manager_validated=True,
        )
