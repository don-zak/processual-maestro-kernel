"""Governed operator sandbox reference-intake contracts.

This module accepts reference names only. It does not accept endpoint URLs,
credentials, tokens, certificates, payloads, or secret values. It does not
read environment variables, persist submissions, create bindings, resolve
credentials, invoke a transport, open a network connection, expose a route,
enable runtime execution, or authorize production.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "OPERATOR_SANDBOX_INTAKE_CONTRACTS",
    "SUPPORTED_OPERATOR_SANDBOX_INTAKES",
    "OperatorSandboxIntakeAssessment",
    "OperatorSandboxIntakeContract",
    "OperatorSandboxIntakeStatus",
    "OperatorSandboxReferenceSubmission",
    "assess_operator_sandbox_intake",
    "get_operator_sandbox_intake_contract",
    "list_operator_sandbox_intake_contracts",
    "normalize_operator_sandbox_intake_id",
    "validate_operator_sandbox_intake_contracts",
    "validate_operator_sandbox_intake_registry",
]


class OperatorSandboxIntakeStatus(StrEnum):
    PENDING_OPERATOR_INPUT = "pending_operator_input"
    REFERENCES_RECEIVED_FOR_REVIEW = (
        "references_received_for_review"
    )
    BLOCKED = "blocked"


_INTAKE_ID: Final[str] = (
    "telecom_ticketing_operator_sandbox_reference_intake"
)
_CONNECTOR_ID: Final[str] = "telecom_ticketing_reference"
_TARGET_REFERENCE_ID: Final[str] = (
    "telecom_ticketing_operator_sandbox_target_reference"
)
_CREDENTIAL_PROFILE_ID: Final[str] = (
    "telecom_operations_api_reference"
)
_SECRET_MANAGER_CONTRACT_ID: Final[str] = (
    "telecom_operations_customer_vault_secret_manager_contract"
)
_PILOT_ID: Final[str] = (
    "telecom_ticketing_read_only_sandbox_pilot"
)

_REQUIRED_INPUT_NAMES: Final[tuple[str, ...]] = (
    "endpoint_reference",
    "auth_method_reference",
    "secret_provider_reference",
    "tenant_reference",
    "scope_reference",
    "tls_policy_reference",
    "allowlist_reference",
    "security_review_reference",
    "operator_approval_reference",
    "kill_switch_reference",
)

_REQUIRED_TRUE_FLAGS: Final[tuple[str, ...]] = (
    "sandbox_only",
    "read_only",
    "reference_only",
    "customer_authorization_required",
    "operator_approval_required",
    "security_review_required",
    "tls_policy_required",
    "allowlist_required",
    "kill_switch_required",
)

_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "endpoint_registered",
    "target_binding_created",
    "secret_reference_registered",
    "credentials_resolved",
    "external_http_enabled",
    "socket_access_enabled",
    "request_execution_allowed",
    "dispatcher_invocation_allowed",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
)

_PROHIBITED_REFERENCE_MARKERS: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "://",
    "bearer ",
    "basic ",
    "password=",
    "token=",
    "secret=",
    "private_key=",
    "certificate=",
    "client_secret=",
    "api_key=",
    "raw_payload=",
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
            f"{name} must be a reference name, not raw material."
        )

    return normalized


def _validate_reference_tuple(
    name: str,
    values: object,
) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise TypeError(f"{name} must be a tuple.")

    if not values:
        raise ValueError(f"{name} must not be empty.")

    if len(set(values)) != len(values):
        raise ValueError(f"{name} must not contain duplicates.")

    for index, value in enumerate(values):
        _validate_reference(
            f"{name}[{index}]",
            value,
        )

    return values


def normalize_operator_sandbox_intake_id(
    intake_id: str,
) -> str:
    return _validate_reference("intake_id", intake_id)


@dataclass(frozen=True, slots=True)
class OperatorSandboxIntakeContract:
    intake_id: str
    connector_id: str
    environment: str
    access_mode: str
    target_reference_id: str
    credential_profile_id: str
    secret_manager_contract_id: str
    pilot_id: str
    endpoint_reference_name: str
    required_operator_inputs: tuple[str, ...]
    sandbox_only: bool = True
    read_only: bool = True
    reference_only: bool = True
    customer_authorization_required: bool = True
    operator_approval_required: bool = True
    security_review_required: bool = True
    tls_policy_required: bool = True
    allowlist_required: bool = True
    kill_switch_required: bool = True
    status: OperatorSandboxIntakeStatus = (
        OperatorSandboxIntakeStatus.PENDING_OPERATOR_INPUT
    )
    endpoint_registered: bool = False
    target_binding_created: bool = False
    secret_reference_registered: bool = False
    credentials_resolved: bool = False
    external_http_enabled: bool = False
    socket_access_enabled: bool = False
    request_execution_allowed: bool = False
    dispatcher_invocation_allowed: bool = False
    persistence_allowed: bool = False
    background_task_allowed: bool = False
    route_exposure_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False

    def __post_init__(self) -> None:
        for name in (
            "intake_id",
            "connector_id",
            "environment",
            "access_mode",
            "target_reference_id",
            "credential_profile_id",
            "secret_manager_contract_id",
            "pilot_id",
            "endpoint_reference_name",
        ):
            _validate_reference(name, getattr(self, name))

        _validate_reference_tuple(
            "required_operator_inputs",
            self.required_operator_inputs,
        )

        if self.connector_id != _CONNECTOR_ID:
            raise ValueError(
                "R1 intake must remain scoped to telecom ticketing."
            )

        if self.environment != "sandbox":
            raise ValueError(
                "R1 intake must remain sandbox-only."
            )

        if self.access_mode != "read":
            raise ValueError(
                "R1 intake must remain read-only."
            )

        if self.required_operator_inputs != _REQUIRED_INPUT_NAMES:
            raise ValueError(
                "required operator inputs must remain fixed."
            )

        if not isinstance(
            self.status,
            OperatorSandboxIntakeStatus,
        ):
            raise TypeError(
                "status must be OperatorSandboxIntakeStatus."
            )

        if self.status is not (
            OperatorSandboxIntakeStatus
            .PENDING_OPERATOR_INPUT
        ):
            raise ValueError(
                "declared R1 contract must remain pending."
            )

        for name in _REQUIRED_TRUE_FLAGS:
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


@dataclass(frozen=True, slots=True)
class OperatorSandboxReferenceSubmission:
    submission_id: str
    intake_id: str
    endpoint_reference: str
    auth_method_reference: str
    secret_provider_reference: str
    tenant_reference: str
    scope_reference: str
    tls_policy_reference: str
    allowlist_reference: str
    security_review_reference: str
    operator_approval_reference: str
    kill_switch_reference: str

    def __post_init__(self) -> None:
        for name in (
            "submission_id",
            "intake_id",
            *_REQUIRED_INPUT_NAMES,
        ):
            _validate_reference(name, getattr(self, name))

        if self.intake_id != _INTAKE_ID:
            raise ValueError(
                "submission must reference the declared intake."
            )


@dataclass(frozen=True, slots=True)
class OperatorSandboxIntakeAssessment:
    intake_id: str
    connector_id: str
    status: OperatorSandboxIntakeStatus
    contract_valid: bool
    submission_present: bool
    reference_count: int
    required_reference_count: int
    references_valid: bool
    ready_for_reference_review: bool
    endpoint_registered: bool
    target_binding_created: bool
    secret_reference_registered: bool
    credentials_resolved: bool
    external_http_enabled: bool
    socket_access_enabled: bool
    request_execution_allowed: bool
    dispatcher_invocation_allowed: bool
    persistence_allowed: bool
    background_task_allowed: bool
    route_exposure_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    automatic_activation_allowed: bool
    blocker_codes: tuple[str, ...]


_DECLARED_CONTRACT: Final[OperatorSandboxIntakeContract] = (
    OperatorSandboxIntakeContract(
        intake_id=_INTAKE_ID,
        connector_id=_CONNECTOR_ID,
        environment="sandbox",
        access_mode="read",
        target_reference_id=_TARGET_REFERENCE_ID,
        credential_profile_id=_CREDENTIAL_PROFILE_ID,
        secret_manager_contract_id=(
            _SECRET_MANAGER_CONTRACT_ID
        ),
        pilot_id=_PILOT_ID,
        endpoint_reference_name=(
            "operator_sandbox_endpoint_reference_pending"
        ),
        required_operator_inputs=_REQUIRED_INPUT_NAMES,
    )
)

OPERATOR_SANDBOX_INTAKE_CONTRACTS = MappingProxyType(
    {
        _DECLARED_CONTRACT.intake_id: _DECLARED_CONTRACT
    }
)

SUPPORTED_OPERATOR_SANDBOX_INTAKES = tuple(
    OPERATOR_SANDBOX_INTAKE_CONTRACTS
)


def list_operator_sandbox_intake_contracts(
) -> tuple[OperatorSandboxIntakeContract, ...]:
    return tuple(
        OPERATOR_SANDBOX_INTAKE_CONTRACTS.values()
    )


def get_operator_sandbox_intake_contract(
    intake_id: str,
) -> OperatorSandboxIntakeContract:
    normalized = normalize_operator_sandbox_intake_id(
        intake_id
    )

    try:
        return OPERATOR_SANDBOX_INTAKE_CONTRACTS[
            normalized
        ]
    except KeyError as exc:
        raise KeyError(
            f"unknown operator sandbox intake: {normalized}"
        ) from exc


def _contract_validation_issues(
    contract: OperatorSandboxIntakeContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    if not isinstance(
        contract,
        OperatorSandboxIntakeContract,
    ):
        return ("invalid_intake_contract_type",)

    if contract.connector_id != _CONNECTOR_ID:
        issues.append("connector_reference_mismatch")

    if contract.environment != "sandbox":
        issues.append("environment_must_be_sandbox")

    if contract.access_mode != "read":
        issues.append("access_mode_must_be_read")

    if contract.required_operator_inputs != _REQUIRED_INPUT_NAMES:
        issues.append("required_input_contract_mismatch")

    for name in _REQUIRED_TRUE_FLAGS:
        if getattr(contract, name) is not True:
            issues.append(f"{name}_required")

    for name in _UNSAFE_CONTRACT_FLAGS:
        if getattr(contract, name) is not False:
            issues.append(f"{name}_must_remain_disabled")

    return tuple(issues)


def validate_operator_sandbox_intake_contracts(
    contracts: Iterable[OperatorSandboxIntakeContract],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, contract in enumerate(contracts):
        if not isinstance(
            contract,
            OperatorSandboxIntakeContract,
        ):
            issues.append(
                f"contract_{index}:invalid_intake_contract_type"
            )
            continue

        if contract.intake_id in seen_ids:
            issues.append(
                f"{contract.intake_id}:duplicate_intake_id"
            )

        seen_ids.add(contract.intake_id)

        for issue in _contract_validation_issues(contract):
            issues.append(f"{contract.intake_id}:{issue}")

    if not seen_ids:
        issues.append("no_operator_sandbox_intake_declared")

    return tuple(issues)


def validate_operator_sandbox_intake_registry(
) -> tuple[str, ...]:
    issues = list(
        validate_operator_sandbox_intake_contracts(
            list_operator_sandbox_intake_contracts()
        )
    )

    if tuple(
        OPERATOR_SANDBOX_INTAKE_CONTRACTS
    ) != SUPPORTED_OPERATOR_SANDBOX_INTAKES:
        issues.append("supported_intake_order_mismatch")

    for key, contract in (
        OPERATOR_SANDBOX_INTAKE_CONTRACTS.items()
    ):
        if key != contract.intake_id:
            issues.append(f"{key}:registry_key_mismatch")

    return tuple(issues)


def assess_operator_sandbox_intake(
    intake_id: str,
    submission: OperatorSandboxReferenceSubmission | None = None,
) -> OperatorSandboxIntakeAssessment:
    contract = get_operator_sandbox_intake_contract(
        intake_id
    )
    contract_issues = _contract_validation_issues(contract)
    contract_valid = not contract_issues

    if submission is None:
        submission_present = False
        references_valid = False
        reference_count = 0
        status = (
            OperatorSandboxIntakeStatus
            .PENDING_OPERATOR_INPUT
        )
    elif not isinstance(
        submission,
        OperatorSandboxReferenceSubmission,
    ):
        raise TypeError(
            "submission must be "
            "OperatorSandboxReferenceSubmission or None."
        )
    elif submission.intake_id != contract.intake_id:
        submission_present = True
        references_valid = False
        reference_count = 0
        status = OperatorSandboxIntakeStatus.BLOCKED
    else:
        submission_present = True
        reference_values = tuple(
            getattr(submission, name)
            for name in _REQUIRED_INPUT_NAMES
        )
        references_valid = all(
            isinstance(value, str) and bool(value)
            for value in reference_values
        )
        reference_count = len(reference_values)
        status = (
            OperatorSandboxIntakeStatus
            .REFERENCES_RECEIVED_FOR_REVIEW
            if contract_valid and references_valid
            else OperatorSandboxIntakeStatus.BLOCKED
        )

    ready = (
        contract_valid
        and submission_present
        and references_valid
        and reference_count == len(_REQUIRED_INPUT_NAMES)
    )

    blockers = list(contract_issues)

    if not submission_present:
        blockers.extend(
            f"{name}_pending"
            for name in _REQUIRED_INPUT_NAMES
        )

    if submission_present and not references_valid:
        blockers.append("submitted_references_invalid")

    blockers.extend(
        (
            "endpoint_registration_disabled",
            "target_binding_creation_disabled",
            "secret_reference_registration_disabled",
            "credential_resolution_disabled",
            "external_http_disabled",
            "socket_access_disabled",
            "request_execution_disabled",
            "dispatcher_invocation_disabled",
            "persistence_disabled",
            "background_tasks_disabled",
            "route_exposure_disabled",
            "runtime_disabled",
            "production_disabled",
            "automatic_activation_disabled",
        )
    )

    return OperatorSandboxIntakeAssessment(
        intake_id=contract.intake_id,
        connector_id=contract.connector_id,
        status=status,
        contract_valid=contract_valid,
        submission_present=submission_present,
        reference_count=reference_count,
        required_reference_count=len(_REQUIRED_INPUT_NAMES),
        references_valid=references_valid,
        ready_for_reference_review=ready,
        endpoint_registered=False,
        target_binding_created=False,
        secret_reference_registered=False,
        credentials_resolved=False,
        external_http_enabled=False,
        socket_access_enabled=False,
        request_execution_allowed=False,
        dispatcher_invocation_allowed=False,
        persistence_allowed=False,
        background_task_allowed=False,
        route_exposure_allowed=False,
        runtime_enabled=False,
        production_allowed=False,
        automatic_activation_allowed=False,
        blocker_codes=tuple(blockers),
    )
