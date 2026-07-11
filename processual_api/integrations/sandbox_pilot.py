"""Governed read-only sandbox pilot intake contracts.

This module selects one existing telecom ticketing read plan and projects its
current readiness state without enabling transport, HTTP, credential
resolution, persistence, runtime execution, or production access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.connector_bindings import (
    CONNECTOR_ENVIRONMENT_BINDINGS,
    CONNECTOR_SECRET_REFERENCES,
    CONNECTOR_TARGET_REFERENCES,
    ConnectorEnvironmentBinding,
    ConnectorSecretReference,
    ConnectorTargetReference,
)
from processual_api.integrations.connector_registry import (
    RUNTIME_CONNECTOR_CONTRACTS,
)
from processual_api.integrations.operation_plans import (
    CONNECTOR_OPERATION_PLANS,
    ConnectorOperationPlan,
)

__all__ = [
    "CONNECTOR_SANDBOX_PILOT_CONTRACTS",
    "SUPPORTED_CONNECTOR_SANDBOX_PILOT_CONTRACTS",
    "ConnectorSandboxPilotAssessment",
    "ConnectorSandboxPilotContract",
    "ConnectorSandboxPilotStatus",
    "assess_connector_sandbox_pilot",
    "get_connector_sandbox_pilot_contract",
    "list_connector_sandbox_pilot_contracts",
    "normalize_connector_sandbox_pilot_id",
    "validate_connector_sandbox_pilot_contracts",
    "validate_connector_sandbox_pilot_registry",
]


class ConnectorSandboxPilotStatus(StrEnum):
    """Safe non-executing states for a sandbox pilot declaration."""

    PENDING_OPERATOR_INPUT = "pending_operator_input"
    BLOCKED = "blocked"


_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "action_execution_allowed",
    "runtime_enabled",
    "external_http_enabled",
    "production_allowed",
    "automatic_activation_allowed",
    "credentials_resolved",
)

_PROHIBITED_REFERENCE_MARKERS: Final[tuple[str, ...]] = (
    "http://",
    "https://",
    "bearer ",
    "password=",
    "token=",
    "secret=",
    "private_key",
    "raw_payload",
)

_REQUIRED_PILOT_INPUT_IDS: Final[tuple[str, ...]] = (
    "approved_sandbox_endpoint_reference",
    "operator_or_customer_approval_reference",
    "external_api_name_reference",
    "external_api_version_reference",
    "authentication_method_reference",
    "secret_manager_reference",
    "test_tenant_reference",
    "data_classification_reference",
    "allowed_scope_reference",
    "rate_limit_reference",
    "timeout_policy_reference",
    "retention_policy_reference",
    "audit_owner_reference",
    "incident_contact_reference",
    "acceptance_criteria_reference",
)

_SELECTED_PILOT_ID: Final[str] = (
    "telecom_ticketing_read_only_sandbox_pilot"
)

_SELECTED_CONNECTOR_ID: Final[str] = (
    "telecom_ticketing_reference"
)

_SELECTED_BINDING_ID: Final[str] = (
    "telecom_ticketing_reference_sandbox_binding"
)

_SELECTED_TARGET_REFERENCE_ID: Final[str] = (
    "telecom_ticketing_reference_sandbox_target_reference"
)

_SELECTED_SECRET_REFERENCE_IDS: Final[tuple[str, ...]] = (
    "telecom_operations_api_reference_secret_reference",
)

_SELECTED_CREDENTIAL_PROFILE_IDS: Final[tuple[str, ...]] = (
    "telecom_operations_api_reference",
)

_TICKETING_READ_CANDIDATE_PLAN_IDS: Final[tuple[str, ...]] = (
    "telecom_ticketing_reference_sandbox_helpdesk_read_operation_plan",
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan",
)

_SELECTED_OPERATION_PLAN_ID: Final[str] = (
    "telecom_ticketing_reference_sandbox_ticket_read_operation_plan"
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
        _validate_reference_text(field_name, value)


@dataclass(frozen=True, slots=True)
class ConnectorSandboxPilotContract:
    """Reference-only declaration for one governed sandbox pilot."""

    pilot_id: str
    connector_id: str
    environment: str
    access_mode: str
    candidate_plan_ids: tuple[str, ...]
    selected_plan_id: str
    binding_id: str
    target_reference_id: str
    secret_reference_ids: tuple[str, ...]
    credential_profile_ids: tuple[str, ...]
    required_input_ids: tuple[str, ...]
    operator_approval_required: bool
    customer_approval_required: bool
    sandbox_only: bool
    read_only: bool
    status: ConnectorSandboxPilotStatus = (
        ConnectorSandboxPilotStatus.PENDING_OPERATOR_INPUT
    )
    configured: bool = False
    validated: bool = False
    approved: bool = False
    action_execution_allowed: bool = False
    runtime_enabled: bool = False
    external_http_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False
    credentials_resolved: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "pilot_id",
            "connector_id",
            "environment",
            "access_mode",
            "selected_plan_id",
            "binding_id",
            "target_reference_id",
        ):
            _validate_reference_text(
                field_name,
                getattr(self, field_name),
            )

        for field_name in (
            "candidate_plan_ids",
            "secret_reference_ids",
            "credential_profile_ids",
            "required_input_ids",
        ):
            _validate_reference_sequence(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.status,
            ConnectorSandboxPilotStatus,
        ):
            try:
                normalized_status = ConnectorSandboxPilotStatus(
                    self.status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported sandbox pilot status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        if self.environment != "sandbox":
            raise ValueError(
                "Sandbox pilot environment must remain sandbox."
            )

        if self.access_mode != "read":
            raise ValueError(
                "The initial sandbox pilot must remain read-only."
            )

        if self.selected_plan_id not in self.candidate_plan_ids:
            raise ValueError(
                "Selected plan must exist in candidate_plan_ids."
            )

        if self.operator_approval_required is not True:
            raise ValueError(
                "Operator approval must remain required."
            )

        if self.customer_approval_required is not True:
            raise ValueError(
                "Customer approval must remain required."
            )

        if self.sandbox_only is not True:
            raise ValueError(
                "The pilot must remain sandbox-only."
            )

        if self.read_only is not True:
            raise ValueError(
                "The pilot must remain read-only."
            )

        if (
            self.status
            is not ConnectorSandboxPilotStatus.PENDING_OPERATOR_INPUT
        ):
            raise ValueError(
                "The R1 pilot must remain pending operator input."
            )

        for flag_name in (
            "configured",
            "validated",
            "approved",
            *_UNSAFE_CONTRACT_FLAGS,
        ):
            if getattr(self, flag_name) is not False:
                raise ValueError(
                    f"{flag_name} must remain False in 16E-R1."
                )


@dataclass(frozen=True, slots=True)
class ConnectorSandboxPilotAssessment:
    """Immutable projection of the current non-executing pilot state."""

    pilot_id: str
    status: ConnectorSandboxPilotStatus
    contract_valid: bool
    reference_graph_valid: bool
    operator_inputs_complete: bool
    customer_approval_present: bool
    operator_approval_present: bool
    sandbox_target_configured: bool
    sandbox_target_validated: bool
    sandbox_target_approved: bool
    sandbox_binding_configured: bool
    sandbox_binding_validated: bool
    sandbox_binding_approved: bool
    credentials_resolved: bool
    runtime_enabled: bool
    external_http_enabled: bool
    dispatch_allowed: bool
    production_allowed: bool
    action_execution_allowed: bool
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_reference_text(
            "pilot_id",
            self.pilot_id,
        )

        if not isinstance(
            self.status,
            ConnectorSandboxPilotStatus,
        ):
            try:
                normalized_status = ConnectorSandboxPilotStatus(
                    self.status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported sandbox pilot assessment status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        boolean_fields = (
            "contract_valid",
            "reference_graph_valid",
            "operator_inputs_complete",
            "customer_approval_present",
            "operator_approval_present",
            "sandbox_target_configured",
            "sandbox_target_validated",
            "sandbox_target_approved",
            "sandbox_binding_configured",
            "sandbox_binding_validated",
            "sandbox_binding_approved",
            "credentials_resolved",
            "runtime_enabled",
            "external_http_enabled",
            "dispatch_allowed",
            "production_allowed",
            "action_execution_allowed",
        )

        for field_name in boolean_fields:
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        _validate_reference_sequence(
            "blocker_codes",
            self.blocker_codes,
        )

        for flag_name in (
            "credentials_resolved",
            "runtime_enabled",
            "external_http_enabled",
            "dispatch_allowed",
            "production_allowed",
            "action_execution_allowed",
        ):
            if getattr(self, flag_name) is not False:
                raise ValueError(
                    f"{flag_name} must remain False in 16E-R1."
                )


def normalize_connector_sandbox_pilot_id(
    pilot_id: str,
) -> str:
    """Normalize a sandbox pilot identifier without accepting raw data."""

    if not isinstance(pilot_id, str):
        raise TypeError("pilot_id must be a string.")

    normalized = pilot_id.strip().casefold()

    _validate_reference_text(
        "pilot_id",
        normalized,
    )

    return normalized


def _plan_is_safe_read_only_sandbox(
    plan: ConnectorOperationPlan,
    *,
    connector_id: str,
    binding_id: str,
) -> bool:
    if plan.connector_id != connector_id:
        return False

    if plan.binding_id != binding_id:
        return False

    if _enum_value(plan.environment) != "sandbox":
        return False

    if _enum_value(plan.access_mode) != "read":
        return False

    if _enum_value(plan.status) != "planning_only":
        return False

    if not plan.steps:
        return False

    if _enum_value(plan.steps[-1].step_kind) != "block_dispatch":
        return False

    for flag_name in (
        "action_execution_allowed",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "credentials_resolution_allowed",
    ):
        if getattr(plan, flag_name) is not False:
            return False

    for step in plan.steps:
        if step.execution_allowed is not False:
            return False

        if step.external_http_allowed is not False:
            return False

        if step.credentials_resolution_allowed is not False:
            return False

    return True


def _binding_is_default_deny(
    binding: ConnectorEnvironmentBinding,
) -> bool:
    if _enum_value(binding.environment) != "sandbox":
        return False

    for flag_name in (
        "configured",
        "validated",
        "approved",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "credentials_resolved",
    ):
        if getattr(binding, flag_name) is not False:
            return False

    return True


def _target_is_default_deny(
    target: ConnectorTargetReference,
) -> bool:
    if _enum_value(target.environment) != "sandbox":
        return False

    for flag_name in (
        "configured",
        "validated",
        "approved",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
    ):
        if getattr(target, flag_name) is not False:
            return False

    return True


def _secret_reference_is_default_deny(
    secret_reference: ConnectorSecretReference,
) -> bool:
    if secret_reference.value_stored is not False:
        return False

    if secret_reference.raw_secret_visible is not False:
        return False

    if secret_reference.credentials_resolved is not False:
        return False

    if secret_reference.runtime_enabled is not False:
        return False

    if secret_reference.production_allowed is not False:
        return False

    return True


def _contract_validation_issues(
    contract: ConnectorSandboxPilotContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    connector = RUNTIME_CONNECTOR_CONTRACTS.get(
        contract.connector_id
    )

    binding = CONNECTOR_ENVIRONMENT_BINDINGS.get(
        contract.binding_id
    )

    target = CONNECTOR_TARGET_REFERENCES.get(
        contract.target_reference_id
    )

    selected_plan = CONNECTOR_OPERATION_PLANS.get(
        contract.selected_plan_id
    )

    if connector is None:
        issues.append(
            f"{contract.pilot_id}:connector_not_found"
        )
    else:
        if contract.environment not in connector.supported_environments:
            issues.append(
                f"{contract.pilot_id}:sandbox_environment_unsupported"
            )

        if contract.credential_profile_ids != (
            connector.authentication_profile_ids
        ):
            issues.append(
                f"{contract.pilot_id}:credential_profile_mismatch"
            )

        if connector.external_api_version != "pending_operator_input":
            issues.append(
                f"{contract.pilot_id}:external_api_version_not_pending"
            )

        for flag_name in (
            "read_allowed",
            "write_allowed",
            "runtime_enabled",
            "external_http_enabled",
            "production_allowed",
            "automatic_activation_allowed",
            "credentials_storage_allowed",
            "raw_secret_visible",
        ):
            if getattr(connector, flag_name) is not False:
                issues.append(
                    f"{contract.pilot_id}:unsafe_connector_{flag_name}"
                )

    if binding is None:
        issues.append(
            f"{contract.pilot_id}:binding_not_found"
        )
    else:
        if binding.connector_id != contract.connector_id:
            issues.append(
                f"{contract.pilot_id}:binding_connector_mismatch"
            )

        if binding.target_reference_id != contract.target_reference_id:
            issues.append(
                f"{contract.pilot_id}:binding_target_mismatch"
            )

        if binding.secret_reference_ids != contract.secret_reference_ids:
            issues.append(
                f"{contract.pilot_id}:binding_secret_mismatch"
            )

        if not _binding_is_default_deny(binding):
            issues.append(
                f"{contract.pilot_id}:binding_not_default_deny"
            )

    if target is None:
        issues.append(
            f"{contract.pilot_id}:target_not_found"
        )
    else:
        if target.connector_id != contract.connector_id:
            issues.append(
                f"{contract.pilot_id}:target_connector_mismatch"
            )

        if not _target_is_default_deny(target):
            issues.append(
                f"{contract.pilot_id}:target_not_default_deny"
            )

    if selected_plan is None:
        issues.append(
            f"{contract.pilot_id}:selected_plan_not_found"
        )
    elif not _plan_is_safe_read_only_sandbox(
        selected_plan,
        connector_id=contract.connector_id,
        binding_id=contract.binding_id,
    ):
        issues.append(
            f"{contract.pilot_id}:selected_plan_not_safe"
        )

    for candidate_plan_id in contract.candidate_plan_ids:
        candidate_plan = CONNECTOR_OPERATION_PLANS.get(
            candidate_plan_id
        )

        if candidate_plan is None:
            issues.append(
                f"{contract.pilot_id}:candidate_plan_not_found:"
                f"{candidate_plan_id}"
            )
            continue

        if not _plan_is_safe_read_only_sandbox(
            candidate_plan,
            connector_id=contract.connector_id,
            binding_id=contract.binding_id,
        ):
            issues.append(
                f"{contract.pilot_id}:candidate_plan_not_safe:"
                f"{candidate_plan_id}"
            )

    secret_profile_ids: list[str] = []

    for secret_reference_id in contract.secret_reference_ids:
        secret_reference = CONNECTOR_SECRET_REFERENCES.get(
            secret_reference_id
        )

        if secret_reference is None:
            issues.append(
                f"{contract.pilot_id}:secret_reference_not_found:"
                f"{secret_reference_id}"
            )
            continue

        secret_profile_ids.append(
            secret_reference.credential_profile_id
        )

        if not _secret_reference_is_default_deny(
            secret_reference
        ):
            issues.append(
                f"{contract.pilot_id}:secret_reference_not_default_deny:"
                f"{secret_reference_id}"
            )

    if tuple(secret_profile_ids) != contract.credential_profile_ids:
        issues.append(
            f"{contract.pilot_id}:secret_profile_mismatch"
        )

    return tuple(issues)


def validate_connector_sandbox_pilot_contracts(
    contracts: tuple[ConnectorSandboxPilotContract, ...],
) -> tuple[str, ...]:
    """Validate sandbox pilot contracts against existing governed registries."""

    issues: list[str] = []
    seen_ids: set[str] = set()

    for contract in contracts:
        if not isinstance(
            contract,
            ConnectorSandboxPilotContract,
        ):
            issues.append(
                "sandbox_pilot_contract_type_invalid"
            )
            continue

        if contract.pilot_id in seen_ids:
            issues.append(
                f"{contract.pilot_id}:duplicate_pilot_id"
            )

        seen_ids.add(contract.pilot_id)
        issues.extend(
            _contract_validation_issues(contract)
        )

    return tuple(issues)


_TELECOM_TICKETING_READ_ONLY_SANDBOX_PILOT = (
    ConnectorSandboxPilotContract(
        pilot_id=_SELECTED_PILOT_ID,
        connector_id=_SELECTED_CONNECTOR_ID,
        environment="sandbox",
        access_mode="read",
        candidate_plan_ids=_TICKETING_READ_CANDIDATE_PLAN_IDS,
        selected_plan_id=_SELECTED_OPERATION_PLAN_ID,
        binding_id=_SELECTED_BINDING_ID,
        target_reference_id=_SELECTED_TARGET_REFERENCE_ID,
        secret_reference_ids=_SELECTED_SECRET_REFERENCE_IDS,
        credential_profile_ids=_SELECTED_CREDENTIAL_PROFILE_IDS,
        required_input_ids=_REQUIRED_PILOT_INPUT_IDS,
        operator_approval_required=True,
        customer_approval_required=True,
        sandbox_only=True,
        read_only=True,
    )
)

_CONNECTOR_SANDBOX_PILOT_CONTRACTS = {
    _TELECOM_TICKETING_READ_ONLY_SANDBOX_PILOT.pilot_id: (
        _TELECOM_TICKETING_READ_ONLY_SANDBOX_PILOT
    ),
}

CONNECTOR_SANDBOX_PILOT_CONTRACTS = MappingProxyType(
    _CONNECTOR_SANDBOX_PILOT_CONTRACTS
)

SUPPORTED_CONNECTOR_SANDBOX_PILOT_CONTRACTS = tuple(
    CONNECTOR_SANDBOX_PILOT_CONTRACTS
)


def list_connector_sandbox_pilot_contracts(
) -> tuple[ConnectorSandboxPilotContract, ...]:
    """List immutable sandbox pilot declarations."""

    return tuple(
        CONNECTOR_SANDBOX_PILOT_CONTRACTS.values()
    )


def get_connector_sandbox_pilot_contract(
    pilot_id: str,
) -> ConnectorSandboxPilotContract:
    """Return one sandbox pilot declaration by normalized identifier."""

    normalized_id = normalize_connector_sandbox_pilot_id(
        pilot_id
    )

    try:
        return CONNECTOR_SANDBOX_PILOT_CONTRACTS[
            normalized_id
        ]
    except KeyError as exc:
        raise KeyError(
            f"Unknown connector sandbox pilot: {normalized_id}"
        ) from exc


def validate_connector_sandbox_pilot_registry(
) -> tuple[str, ...]:
    """Validate the immutable built-in sandbox pilot registry."""

    return validate_connector_sandbox_pilot_contracts(
        list_connector_sandbox_pilot_contracts()
    )


def assess_connector_sandbox_pilot(
    pilot_id: str,
) -> ConnectorSandboxPilotAssessment:
    """Project current blockers without resolving secrets or using transport."""

    contract = get_connector_sandbox_pilot_contract(
        pilot_id
    )

    contract_issues = _contract_validation_issues(
        contract
    )

    connector = RUNTIME_CONNECTOR_CONTRACTS.get(
        contract.connector_id
    )

    binding = CONNECTOR_ENVIRONMENT_BINDINGS.get(
        contract.binding_id
    )

    target = CONNECTOR_TARGET_REFERENCES.get(
        contract.target_reference_id
    )

    secret_references = tuple(
        CONNECTOR_SECRET_REFERENCES.get(reference_id)
        for reference_id in contract.secret_reference_ids
    )

    blockers: list[str] = []

    if contract_issues:
        blockers.append("pilot_contract_invalid")

    blockers.extend(
        (
            "operator_inputs_pending",
            "customer_approval_pending",
            "operator_approval_pending",
        )
    )

    if connector is None:
        blockers.append("runtime_connector_missing")
    else:
        if connector.external_api_version == "pending_operator_input":
            blockers.append("external_api_version_pending")

        if connector.runtime_enabled is False:
            blockers.append("runtime_disabled")

        if connector.external_http_enabled is False:
            blockers.append("external_http_disabled")

    if binding is None:
        blockers.append("sandbox_binding_missing")
    else:
        if binding.configured is False:
            blockers.append("sandbox_binding_unconfigured")

        if binding.validated is False:
            blockers.append("sandbox_binding_unvalidated")

        if binding.approved is False:
            blockers.append("sandbox_binding_unapproved")

    if target is None:
        blockers.append("sandbox_target_missing")
    else:
        if target.configured is False:
            blockers.append("sandbox_target_unconfigured")

        if target.validated is False:
            blockers.append("sandbox_target_unvalidated")

        if target.approved is False:
            blockers.append("sandbox_target_unapproved")

    if (
        not secret_references
        or any(reference is None for reference in secret_references)
    ):
        blockers.append("secret_reference_missing")
    elif any(
        reference.credentials_resolved is False
        for reference in secret_references
        if reference is not None
    ):
        blockers.append("secret_reference_unresolved")

    unique_blockers = tuple(dict.fromkeys(blockers))

    status = (
        ConnectorSandboxPilotStatus.BLOCKED
        if contract_issues
        else ConnectorSandboxPilotStatus.PENDING_OPERATOR_INPUT
    )

    return ConnectorSandboxPilotAssessment(
        pilot_id=contract.pilot_id,
        status=status,
        contract_valid=not contract_issues,
        reference_graph_valid=not contract_issues,
        operator_inputs_complete=False,
        customer_approval_present=False,
        operator_approval_present=False,
        sandbox_target_configured=(
            bool(target) and target.configured
        ),
        sandbox_target_validated=(
            bool(target) and target.validated
        ),
        sandbox_target_approved=(
            bool(target) and target.approved
        ),
        sandbox_binding_configured=(
            bool(binding) and binding.configured
        ),
        sandbox_binding_validated=(
            bool(binding) and binding.validated
        ),
        sandbox_binding_approved=(
            bool(binding) and binding.approved
        ),
        credentials_resolved=False,
        runtime_enabled=False,
        external_http_enabled=False,
        dispatch_allowed=False,
        production_allowed=False,
        action_execution_allowed=False,
        blocker_codes=unique_blockers,
    )
