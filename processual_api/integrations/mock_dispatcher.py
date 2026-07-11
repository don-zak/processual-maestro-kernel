"""Disabled local connector-dispatch simulation contracts.

The contracts in this module validate reference-only operation metadata and
always preserve default-deny behavior. They perform no network, credential,
storage, audit, worker, sandbox, or production operation.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Final

from processual_api.integrations.operation_plans import (
    CONNECTOR_OPERATION_PLANS,
    ConnectorOperationPlan,
)

__all__ = [
    "ConnectorDispatchRequest",
    "ConnectorDispatchResult",
    "ConnectorDispatchStatus",
    "ConnectorMockDispatcher",
]


class ConnectorDispatchStatus(StrEnum):
    """Safe outcomes supported by the disabled local dispatcher."""

    BLOCKED = "blocked"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN_PLAN = "unknown_plan"
    METADATA_INCOMPLETE = "metadata_incomplete"
    APPROVAL_REFERENCE_MISSING = "approval_reference_missing"
    EXPIRED_REFERENCE = "expired_reference"


_RESULT_EXECUTION_FLAGS: Final[tuple[str, ...]] = (
    "dispatch_attempted",
    "operation_executed",
    "external_http_used",
    "credentials_resolved",
    "payload_persisted",
    "audit_event_emitted",
    "background_task_created",
    "production_used",
)

_PLAN_EXECUTION_FLAGS: Final[tuple[str, ...]] = (
    "action_execution_allowed",
    "runtime_enabled",
    "external_http_enabled",
    "production_allowed",
    "automatic_activation_allowed",
    "credentials_resolution_allowed",
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


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _validate_reference_text(
    field_name: str,
    value: object,
) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

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


@dataclass(frozen=True, slots=True)
class ConnectorDispatchRequest:
    """Reference-only request for a local blocked-dispatch simulation."""

    request_id: str
    plan_id: str
    operation_id: str
    tenant_reference: str
    payload_hash: str
    idempotency_key: str
    requested_at_reference: str
    expires_at_reference: str
    requester_reference: str
    approval_reference: str
    simulation_mode: bool

    def __post_init__(self) -> None:
        if self.simulation_mode is not True:
            raise ValueError(
                "Connector dispatch requests must remain in simulation mode."
            )

        for definition in fields(self):
            if definition.name == "simulation_mode":
                continue

            _validate_reference_text(
                definition.name,
                getattr(self, definition.name),
            )


@dataclass(frozen=True, slots=True)
class ConnectorDispatchResult:
    """Immutable default-deny result from the local dispatcher."""

    request_id: str
    plan_id: str
    dispatch_status: ConnectorDispatchStatus
    reason_code: str
    reason: str
    validated_plan: bool
    validated_metadata: bool
    dispatch_attempted: bool = False
    operation_executed: bool = False
    external_http_used: bool = False
    credentials_resolved: bool = False
    payload_persisted: bool = False
    audit_event_emitted: bool = False
    background_task_created: bool = False
    production_used: bool = False

    def __post_init__(self) -> None:
        if not isinstance(
            self.dispatch_status,
            ConnectorDispatchStatus,
        ):
            try:
                normalized_status = ConnectorDispatchStatus(
                    self.dispatch_status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported connector dispatch status."
                ) from exc

            object.__setattr__(
                self,
                "dispatch_status",
                normalized_status,
            )

        for field_name in (
            "request_id",
            "plan_id",
            "reason_code",
            "reason",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{field_name} must be a non-empty string."
                )

        if type(self.validated_plan) is not bool:
            raise TypeError("validated_plan must be a boolean.")

        if type(self.validated_metadata) is not bool:
            raise TypeError("validated_metadata must be a boolean.")

        for flag_name in _RESULT_EXECUTION_FLAGS:
            if getattr(self, flag_name) is not False:
                raise ValueError(
                    f"{flag_name} must remain False in mock results."
                )


def _plan_is_default_deny(
    plan: ConnectorOperationPlan,
) -> bool:
    if _enum_value(plan.status) != "planning_only":
        return False

    if not plan.steps:
        return False

    if _enum_value(plan.steps[-1].step_kind) != "block_dispatch":
        return False

    if any(
        getattr(plan, flag_name) is not False
        for flag_name in _PLAN_EXECUTION_FLAGS
    ):
        return False

    for step in plan.steps:
        if step.execution_allowed is not False:
            return False

        if step.external_http_allowed is not False:
            return False

        if step.credentials_resolution_allowed is not False:
            return False

    return True


def _missing_required_metadata(
    request: ConnectorDispatchRequest,
) -> tuple[str, ...]:
    required_fields = (
        "request_id",
        "plan_id",
        "operation_id",
        "tenant_reference",
        "payload_hash",
        "idempotency_key",
        "requested_at_reference",
        "expires_at_reference",
        "requester_reference",
    )

    return tuple(
        field_name
        for field_name in required_fields
        if not getattr(request, field_name)
    )


def _result(
    request: ConnectorDispatchRequest,
    *,
    status: ConnectorDispatchStatus,
    reason_code: str,
    reason: str,
    validated_plan: bool,
    validated_metadata: bool,
) -> ConnectorDispatchResult:
    return ConnectorDispatchResult(
        request_id=request.request_id or "missing_request_id",
        plan_id=request.plan_id or "missing_plan_id",
        dispatch_status=status,
        reason_code=reason_code,
        reason=reason,
        validated_plan=validated_plan,
        validated_metadata=validated_metadata,
    )


class ConnectorMockDispatcher:
    """Stateless validator that never attempts connector dispatch."""

    __slots__ = ()

    def dispatch(
        self,
        request: ConnectorDispatchRequest,
    ) -> ConnectorDispatchResult:
        if not isinstance(request, ConnectorDispatchRequest):
            raise TypeError(
                "request must be a ConnectorDispatchRequest."
            )

        missing_fields = _missing_required_metadata(request)

        if missing_fields:
            return _result(
                request,
                status=ConnectorDispatchStatus.METADATA_INCOMPLETE,
                reason_code="required_metadata_missing",
                reason=(
                    "Required dispatch metadata is incomplete: "
                    + ", ".join(missing_fields)
                ),
                validated_plan=False,
                validated_metadata=False,
            )

        plan = CONNECTOR_OPERATION_PLANS.get(request.plan_id)

        if plan is None:
            return _result(
                request,
                status=ConnectorDispatchStatus.UNKNOWN_PLAN,
                reason_code="unknown_operation_plan",
                reason=(
                    "The referenced operation plan is not registered."
                ),
                validated_plan=False,
                validated_metadata=True,
            )

        if plan.plan_id != request.plan_id:
            return _result(
                request,
                status=ConnectorDispatchStatus.INVALID_REQUEST,
                reason_code="operation_plan_registry_mismatch",
                reason=(
                    "The registry key does not match the operation plan."
                ),
                validated_plan=False,
                validated_metadata=True,
            )

        if not _plan_is_default_deny(plan):
            return _result(
                request,
                status=ConnectorDispatchStatus.BLOCKED,
                reason_code="operation_plan_guardrail_violation",
                reason=(
                    "The operation plan does not satisfy default-deny "
                    "dispatch guardrails."
                ),
                validated_plan=False,
                validated_metadata=True,
            )

        if (
            plan.approval_requirement_id
            and not request.approval_reference
        ):
            return _result(
                request,
                status=(
                    ConnectorDispatchStatus.APPROVAL_REFERENCE_MISSING
                ),
                reason_code="approval_reference_required",
                reason=(
                    "A governed approval reference is required."
                ),
                validated_plan=True,
                validated_metadata=False,
            )

        expiry_reference = request.expires_at_reference.casefold()

        if (
            expiry_reference == "expired"
            or expiry_reference.startswith("expired:")
        ):
            return _result(
                request,
                status=ConnectorDispatchStatus.EXPIRED_REFERENCE,
                reason_code="expiry_reference_rejected",
                reason=(
                    "The supplied expiry reference is marked expired."
                ),
                validated_plan=True,
                validated_metadata=False,
            )

        return _result(
            request,
            status=ConnectorDispatchStatus.BLOCKED,
            reason_code="dispatch_disabled_by_contract",
            reason=(
                "Local validation completed, but connector dispatch "
                "remains disabled by contract."
            ),
            validated_plan=True,
            validated_metadata=True,
        )
