"""Default-deny connector operation planning contracts.

EXTERNAL-CONNECTIVITY-16C declares operation identifiers, binding references,
approval requirements, audit projections, expiry, payload-hash, tenant-binding,
and idempotency requirements. It does not execute actions, resolve credentials,
open external HTTP connections, or approve production operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from processual_api.integrations.connector_bindings import (
    get_connector_environment_binding,
)
from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
    list_runtime_connector_contracts,
)

ConnectorOperationAccess = Literal["read", "write", "restricted"]
ConnectorOperationEnvironment = Literal["sandbox", "production"]
ConnectorOperationPlanStatus = Literal["planning_only"]
ConnectorOperationApprovalStatus = Literal["not_requested"]
ConnectorOperationAuditStatus = Literal["projection_only"]
ConnectorOperationStepKind = Literal[
    "validate_operation_metadata",
    "validate_binding_reference",
    "project_audit_event",
    "block_dispatch",
]

SUPPORTED_CONNECTOR_OPERATION_PLAN_STATUSES: tuple[str, ...] = (
    "planning_only",
)
SUPPORTED_CONNECTOR_OPERATION_APPROVAL_STATUSES: tuple[str, ...] = (
    "not_requested",
)
SUPPORTED_CONNECTOR_OPERATION_AUDIT_STATUSES: tuple[str, ...] = (
    "projection_only",
)
SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS: tuple[str, ...] = (
    "validate_operation_metadata",
    "validate_binding_reference",
    "project_audit_event",
    "block_dispatch",
)

_REQUIRED_AUDIT_FIELDS: tuple[str, ...] = (
    "operation_id",
    "plan_id",
    "connector_id",
    "binding_id",
    "capability_id",
    "scope_id",
    "environment",
    "tenant_id",
    "payload_hash",
    "idempotency_key",
    "requester_actor",
    "approver_actor",
    "approval_status",
    "created_at",
    "expires_at",
)


def _normalize_identifier(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _validate_identifier(value: str, field_name: str) -> None:
    normalized = _normalize_identifier(value)
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    if normalized != value:
        raise ValueError(f"{field_name} must be normalized lowercase.")
    if not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(
            f"{field_name} may contain only letters, numbers, and underscores."
        )
    if "://" in value or value.startswith(("http_", "https_")):
        raise ValueError(f"{field_name} cannot contain a literal endpoint.")


def _validate_default_deny(instance: object, fields: tuple[str, ...]) -> None:
    for field_name in fields:
        if getattr(instance, field_name):
            raise ValueError(
                f"{type(instance).__name__} cannot set {field_name}=True in 16C."
            )


@dataclass(frozen=True, slots=True)
class ConnectorOperationStep:
    """One non-executable planning step."""

    step_id: str
    order: int
    step_kind: ConnectorOperationStepKind
    description_reference: str
    required: bool = True
    execution_allowed: bool = False
    external_http_allowed: bool = False
    credentials_resolution_allowed: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.step_id, "step_id")
        _validate_identifier(self.description_reference, "description_reference")
        if self.order < 1:
            raise ValueError("Operation step order must be positive.")
        if self.step_kind not in SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS:
            raise ValueError(f"Unsupported operation step kind '{self.step_kind}'.")
        if not self.required:
            raise ValueError("16C operation steps must remain required.")
        _validate_default_deny(
            self,
            (
                "execution_allowed",
                "external_http_allowed",
                "credentials_resolution_allowed",
            ),
        )


@dataclass(frozen=True, slots=True)
class ConnectorApprovalRequirement:
    """Approval posture projected for one operation plan."""

    approval_requirement_id: str
    plan_id: str
    approval_required: bool
    supervisor_session_required: bool
    requester_approver_separation_required: bool
    expires_before_execution: bool
    invalidated_on_payload_change: bool
    status: ConnectorOperationApprovalStatus = "not_requested"
    satisfied: bool = False
    execution_allowed: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(
            self.approval_requirement_id,
            "approval_requirement_id",
        )
        _validate_identifier(self.plan_id, "plan_id")
        if self.status not in SUPPORTED_CONNECTOR_OPERATION_APPROVAL_STATUSES:
            raise ValueError(
                f"Unsupported operation approval status '{self.status}'."
            )
        expected = self.approval_required
        if self.supervisor_session_required is not expected:
            raise ValueError(
                "Supervisor-session posture must match approval_required."
            )
        if self.requester_approver_separation_required is not expected:
            raise ValueError(
                "Requester/approver separation must match approval_required."
            )
        if self.expires_before_execution is not expected:
            raise ValueError("Approval expiry posture must match approval_required.")
        if self.invalidated_on_payload_change is not expected:
            raise ValueError(
                "Payload-change invalidation must match approval_required."
            )
        _validate_default_deny(
            self,
            ("satisfied", "execution_allowed", "production_allowed"),
        )


@dataclass(frozen=True, slots=True)
class ConnectorAuditProjection:
    """Audit-event schema projection without emitting an event."""

    audit_projection_id: str
    plan_id: str
    event_name: str
    required_fields: tuple[str, ...]
    status: ConnectorOperationAuditStatus = "projection_only"
    persisted: bool = False
    emitted: bool = False
    external_sink_enabled: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.audit_projection_id, "audit_projection_id")
        _validate_identifier(self.plan_id, "plan_id")
        _validate_identifier(self.event_name, "event_name")
        if self.status not in SUPPORTED_CONNECTOR_OPERATION_AUDIT_STATUSES:
            raise ValueError(f"Unsupported operation audit status '{self.status}'.")
        if self.required_fields != _REQUIRED_AUDIT_FIELDS:
            raise ValueError("16C audit projections must preserve required fields.")
        _validate_default_deny(
            self,
            ("persisted", "emitted", "external_sink_enabled"),
        )


@dataclass(frozen=True, slots=True)
class ConnectorOperationPlan:
    """Immutable, non-executable plan for one connector capability."""

    plan_id: str
    connector_id: str
    binding_id: str
    environment: ConnectorOperationEnvironment
    capability_id: str
    scope_id: str
    access_mode: ConnectorOperationAccess
    approval_requirement_id: str
    audit_projection_id: str
    steps: tuple[ConnectorOperationStep, ...]
    requester_approver_separation_required: bool
    status: ConnectorOperationPlanStatus = "planning_only"
    operation_id_required: bool = True
    tenant_binding_required: bool = True
    payload_hash_required: bool = True
    idempotency_key_required: bool = True
    expiry_required: bool = True
    action_execution_allowed: bool = False
    runtime_enabled: bool = False
    external_http_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False
    credentials_resolution_allowed: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.plan_id, "plan_id")
        _validate_identifier(self.connector_id, "connector_id")
        _validate_identifier(self.binding_id, "binding_id")
        _validate_identifier(
            self.approval_requirement_id,
            "approval_requirement_id",
        )
        _validate_identifier(self.audit_projection_id, "audit_projection_id")

        connector = get_runtime_connector_contract(self.connector_id)
        binding = get_connector_environment_binding(self.binding_id)
        if binding.connector_id != self.connector_id:
            raise ValueError("Operation plan binding connector does not match.")
        if binding.environment != self.environment:
            raise ValueError("Operation plan binding environment does not match.")

        capability = next(
            (
                item
                for item in connector.capabilities
                if item.capability_id == self.capability_id
            ),
            None,
        )
        if capability is None:
            raise ValueError(
                f"Unknown capability '{self.capability_id}' for connector "
                f"'{self.connector_id}'."
            )
        if capability.scope_id != self.scope_id:
            raise ValueError("Operation plan scope does not match capability.")
        if capability.access_mode != self.access_mode:
            raise ValueError("Operation plan access mode does not match capability.")
        if capability.sandbox_only and self.environment != "sandbox":
            raise ValueError(
                "Sandbox-only capabilities cannot declare production plans."
            )
        if (
            self.requester_approver_separation_required
            is not capability.approval_required
        ):
            raise ValueError(
                "Operation plan approval separation must match capability posture."
            )
        if self.status not in SUPPORTED_CONNECTOR_OPERATION_PLAN_STATUSES:
            raise ValueError(f"Unsupported operation plan status '{self.status}'.")
        if not all(
            (
                self.operation_id_required,
                self.tenant_binding_required,
                self.payload_hash_required,
                self.idempotency_key_required,
                self.expiry_required,
            )
        ):
            raise ValueError("16C operation metadata requirements cannot be disabled.")
        if len(self.steps) != len(SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS):
            raise ValueError("16C operation plans must declare four planning steps.")
        expected_orders = tuple(range(1, len(self.steps) + 1))
        if tuple(step.order for step in self.steps) != expected_orders:
            raise ValueError("Operation plan step order must be contiguous.")
        if tuple(step.step_kind for step in self.steps) != (
            SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS
        ):
            raise ValueError("Operation plan step kinds must preserve safe ordering.")
        if len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError("Operation plan step ids must be unique.")
        _validate_default_deny(
            self,
            (
                "action_execution_allowed",
                "runtime_enabled",
                "external_http_enabled",
                "production_allowed",
                "automatic_activation_allowed",
                "credentials_resolution_allowed",
            ),
        )


def _plan_identifier(connector_id: str, environment: str, capability_id: str) -> str:
    capability_token = capability_id.replace(".", "_")
    return f"{connector_id}_{environment}_{capability_token}_operation_plan"


def _build_steps(plan_id: str) -> tuple[ConnectorOperationStep, ...]:
    return tuple(
        ConnectorOperationStep(
            step_id=f"{plan_id}_{order}_{step_kind}",
            order=order,
            step_kind=step_kind,
            description_reference=f"{step_kind}_reference",
        )
        for order, step_kind in enumerate(
            SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS,
            start=1,
        )
    )


_OPERATION_PLANS: dict[str, ConnectorOperationPlan] = {}
_APPROVAL_REQUIREMENTS: dict[str, ConnectorApprovalRequirement] = {}
_AUDIT_PROJECTIONS: dict[str, ConnectorAuditProjection] = {}

for _connector in list_runtime_connector_contracts():
    for _capability in _connector.capabilities:
        _environments = (
            ("sandbox",)
            if _capability.sandbox_only
            else _connector.supported_environments
        )
        for _environment in _environments:
            _plan_id = _plan_identifier(
                _connector.connector_id,
                _environment,
                _capability.capability_id,
            )
            _binding_id = f"{_connector.connector_id}_{_environment}_binding"
            _approval_id = f"{_plan_id}_approval_requirement"
            _audit_id = f"{_plan_id}_audit_projection"
            _requires_approval = _capability.approval_required

            _APPROVAL_REQUIREMENTS[_approval_id] = ConnectorApprovalRequirement(
                approval_requirement_id=_approval_id,
                plan_id=_plan_id,
                approval_required=_requires_approval,
                supervisor_session_required=_requires_approval,
                requester_approver_separation_required=_requires_approval,
                expires_before_execution=_requires_approval,
                invalidated_on_payload_change=_requires_approval,
            )
            _AUDIT_PROJECTIONS[_audit_id] = ConnectorAuditProjection(
                audit_projection_id=_audit_id,
                plan_id=_plan_id,
                event_name=f"{_plan_id}_audit_event",
                required_fields=_REQUIRED_AUDIT_FIELDS,
            )
            _OPERATION_PLANS[_plan_id] = ConnectorOperationPlan(
                plan_id=_plan_id,
                connector_id=_connector.connector_id,
                binding_id=_binding_id,
                environment=_environment,
                capability_id=_capability.capability_id,
                scope_id=_capability.scope_id,
                access_mode=_capability.access_mode,
                approval_requirement_id=_approval_id,
                audit_projection_id=_audit_id,
                steps=_build_steps(_plan_id),
                requester_approver_separation_required=_requires_approval,
            )

CONNECTOR_OPERATION_PLANS = MappingProxyType(_OPERATION_PLANS)
CONNECTOR_APPROVAL_REQUIREMENTS = MappingProxyType(_APPROVAL_REQUIREMENTS)
CONNECTOR_AUDIT_PROJECTIONS = MappingProxyType(_AUDIT_PROJECTIONS)

SUPPORTED_CONNECTOR_OPERATION_PLANS: tuple[str, ...] = tuple(
    CONNECTOR_OPERATION_PLANS
)
SUPPORTED_CONNECTOR_APPROVAL_REQUIREMENTS: tuple[str, ...] = tuple(
    CONNECTOR_APPROVAL_REQUIREMENTS
)
SUPPORTED_CONNECTOR_AUDIT_PROJECTIONS: tuple[str, ...] = tuple(
    CONNECTOR_AUDIT_PROJECTIONS
)


def list_connector_operation_plans() -> tuple[ConnectorOperationPlan, ...]:
    return tuple(CONNECTOR_OPERATION_PLANS.values())


def list_connector_approval_requirements() -> tuple[
    ConnectorApprovalRequirement,
    ...,
]:
    return tuple(CONNECTOR_APPROVAL_REQUIREMENTS.values())


def list_connector_audit_projections() -> tuple[ConnectorAuditProjection, ...]:
    return tuple(CONNECTOR_AUDIT_PROJECTIONS.values())


def get_connector_operation_plan(plan_id: str) -> ConnectorOperationPlan:
    normalized_id = _normalize_identifier(plan_id)
    try:
        return CONNECTOR_OPERATION_PLANS[normalized_id]
    except KeyError as exc:
        raise KeyError(f"Unsupported connector operation plan '{plan_id}'.") from exc


def get_connector_approval_requirement(
    approval_requirement_id: str,
) -> ConnectorApprovalRequirement:
    normalized_id = _normalize_identifier(approval_requirement_id)
    try:
        return CONNECTOR_APPROVAL_REQUIREMENTS[normalized_id]
    except KeyError as exc:
        raise KeyError(
            "Unsupported connector approval requirement "
            f"'{approval_requirement_id}'."
        ) from exc


def get_connector_audit_projection(
    audit_projection_id: str,
) -> ConnectorAuditProjection:
    normalized_id = _normalize_identifier(audit_projection_id)
    try:
        return CONNECTOR_AUDIT_PROJECTIONS[normalized_id]
    except KeyError as exc:
        raise KeyError(
            f"Unsupported connector audit projection '{audit_projection_id}'."
        ) from exc


def validate_connector_operation_contracts(
    plans: tuple[ConnectorOperationPlan, ...],
    approvals: tuple[ConnectorApprovalRequirement, ...],
    audits: tuple[ConnectorAuditProjection, ...],
) -> tuple[str, ...]:
    issues: list[str] = []
    plan_ids = tuple(plan.plan_id for plan in plans)
    approval_ids = tuple(
        requirement.approval_requirement_id for requirement in approvals
    )
    audit_ids = tuple(projection.audit_projection_id for projection in audits)

    if len(set(plan_ids)) != len(plan_ids):
        issues.append("Connector operation plan ids must be unique.")
    if len(set(approval_ids)) != len(approval_ids):
        issues.append("Connector approval requirement ids must be unique.")
    if len(set(audit_ids)) != len(audit_ids):
        issues.append("Connector audit projection ids must be unique.")

    expected_keys: set[tuple[str, str, str]] = set()
    for connector in list_runtime_connector_contracts():
        for capability in connector.capabilities:
            environments = (
                ("sandbox",)
                if capability.sandbox_only
                else connector.supported_environments
            )
            for environment in environments:
                expected_keys.add(
                    (
                        connector.connector_id,
                        environment,
                        capability.capability_id,
                    )
                )

    actual_keys = {
        (plan.connector_id, plan.environment, plan.capability_id)
        for plan in plans
    }
    if actual_keys != expected_keys:
        issues.append(
            "Connector operation plans do not cover every allowed capability "
            "environment."
        )

    approvals_by_id = {
        requirement.approval_requirement_id: requirement
        for requirement in approvals
    }
    audits_by_id = {
        projection.audit_projection_id: projection for projection in audits
    }

    for plan in plans:
        approval = approvals_by_id.get(plan.approval_requirement_id)
        if approval is None:
            issues.append(
                f"Plan '{plan.plan_id}' references an unknown approval requirement."
            )
        elif approval.plan_id != plan.plan_id:
            issues.append(
                f"Plan '{plan.plan_id}' approval requirement links another plan."
            )

        audit = audits_by_id.get(plan.audit_projection_id)
        if audit is None:
            issues.append(
                f"Plan '{plan.plan_id}' references an unknown audit projection."
            )
        elif audit.plan_id != plan.plan_id:
            issues.append(
                f"Plan '{plan.plan_id}' audit projection links another plan."
            )

        if any(step.execution_allowed for step in plan.steps):
            issues.append(f"Plan '{plan.plan_id}' contains an executable step.")
        if any(step.external_http_allowed for step in plan.steps):
            issues.append(f"Plan '{plan.plan_id}' contains an HTTP-enabled step.")

    return tuple(issues)


def validate_connector_operation_registry() -> tuple[str, ...]:
    return validate_connector_operation_contracts(
        list_connector_operation_plans(),
        list_connector_approval_requirements(),
        list_connector_audit_projections(),
    )


__all__ = [
    "CONNECTOR_APPROVAL_REQUIREMENTS",
    "CONNECTOR_AUDIT_PROJECTIONS",
    "CONNECTOR_OPERATION_PLANS",
    "SUPPORTED_CONNECTOR_APPROVAL_REQUIREMENTS",
    "SUPPORTED_CONNECTOR_AUDIT_PROJECTIONS",
    "SUPPORTED_CONNECTOR_OPERATION_APPROVAL_STATUSES",
    "SUPPORTED_CONNECTOR_OPERATION_AUDIT_STATUSES",
    "SUPPORTED_CONNECTOR_OPERATION_PLANS",
    "SUPPORTED_CONNECTOR_OPERATION_PLAN_STATUSES",
    "SUPPORTED_CONNECTOR_OPERATION_STEP_KINDS",
    "ConnectorApprovalRequirement",
    "ConnectorAuditProjection",
    "ConnectorOperationAccess",
    "ConnectorOperationApprovalStatus",
    "ConnectorOperationAuditStatus",
    "ConnectorOperationEnvironment",
    "ConnectorOperationPlan",
    "ConnectorOperationPlanStatus",
    "ConnectorOperationStep",
    "ConnectorOperationStepKind",
    "get_connector_approval_requirement",
    "get_connector_audit_projection",
    "get_connector_operation_plan",
    "list_connector_approval_requirements",
    "list_connector_audit_projections",
    "list_connector_operation_plans",
    "validate_connector_operation_contracts",
    "validate_connector_operation_registry",
]
