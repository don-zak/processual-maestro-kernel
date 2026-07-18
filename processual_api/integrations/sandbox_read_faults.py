"""Deterministic sandbox-read fault and safe-refusal contracts.

This module models local synthetic failures around the governed R5 sandbox
read workflow. It never invokes the R5 executor, fake transport, dispatcher,
secret manager, endpoint, network, runtime, route, persistence, retry worker,
or production connector.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.sandbox_read_workflow import (
    ConnectorSandboxReadWorkflowRequest,
    assess_connector_sandbox_read_workflow,
    get_connector_sandbox_read_workflow_contract,
)

__all__ = [
    "CONNECTOR_SANDBOX_READ_FAULT_PROFILES",
    "SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES",
    "ConnectorDeterministicSandboxReadFaultSimulator",
    "ConnectorSandboxReadFaultAssessment",
    "ConnectorSandboxReadFaultKind",
    "ConnectorSandboxReadFaultProfile",
    "ConnectorSandboxReadFaultProfileStatus",
    "ConnectorSandboxReadFaultRequest",
    "ConnectorSandboxReadFaultResult",
    "ConnectorSandboxReadFaultResultStatus",
    "assess_connector_sandbox_read_fault_profile",
    "execute_connector_sandbox_read_fault",
    "get_connector_sandbox_read_fault_profile",
    "list_connector_sandbox_read_fault_profiles",
    "normalize_connector_sandbox_read_fault_profile_id",
    "validate_connector_sandbox_read_fault_profiles",
    "validate_connector_sandbox_read_fault_registry",
]


class ConnectorSandboxReadFaultKind(StrEnum):
    SYNTHETIC_TIMEOUT = "synthetic_timeout"
    SYNTHETIC_TRANSPORT_UNAVAILABLE = (
        "synthetic_transport_unavailable"
    )
    SYNTHETIC_AUTHORIZATION_DENIED = (
        "synthetic_authorization_denied"
    )
    SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE = (
        "synthetic_secret_reference_unavailable"
    )
    SYNTHETIC_PLAN_REJECTED = "synthetic_plan_rejected"
    SYNTHETIC_OPERATOR_APPROVAL_MISSING = (
        "synthetic_operator_approval_missing"
    )
    SYNTHETIC_SECURITY_REVIEW_MISSING = (
        "synthetic_security_review_missing"
    )
    SYNTHETIC_MALFORMED_REFERENCE = (
        "synthetic_malformed_reference"
    )
    SAFE_REFUSAL = "safe_refusal"


class ConnectorSandboxReadFaultProfileStatus(StrEnum):
    LOCAL_FAULT_READY = "local_fault_ready"
    BLOCKED = "blocked"


class ConnectorSandboxReadFaultResultStatus(StrEnum):
    SYNTHETIC_TIMEOUT = "synthetic_timeout"
    SYNTHETIC_TRANSPORT_UNAVAILABLE = (
        "synthetic_transport_unavailable"
    )
    SYNTHETIC_AUTHORIZATION_DENIED = (
        "synthetic_authorization_denied"
    )
    SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE = (
        "synthetic_secret_reference_unavailable"
    )
    SYNTHETIC_PLAN_REJECTED = "synthetic_plan_rejected"
    SYNTHETIC_OPERATOR_APPROVAL_MISSING = (
        "synthetic_operator_approval_missing"
    )
    SYNTHETIC_SECURITY_REVIEW_MISSING = (
        "synthetic_security_review_missing"
    )
    SYNTHETIC_MALFORMED_REFERENCE = (
        "synthetic_malformed_reference"
    )
    SAFE_REFUSAL = "safe_refusal"
    UNKNOWN_FAULT_PROFILE = "unknown_fault_profile"
    INVALID_REQUEST = "invalid_request"
    CONTRACT_BLOCKED = "contract_blocked"


_WORKFLOW_ID: Final[str] = (
    "telecom_ticketing_deterministic_sandbox_read_workflow"
)

_REQUIRED_TRUE_FLAGS: Final[tuple[str, ...]] = (
    "local_only",
    "sandbox_only",
    "read_only",
    "deterministic",
    "immediate_result",
    "synthetic_reference_only",
    "safe_refusal_required",
)

_UNSAFE_PROFILE_FLAGS: Final[tuple[str, ...]] = (
    "real_timeout_wait_allowed",
    "retry_execution_allowed",
    "automatic_retry_allowed",
    "background_retry_allowed",
    "network_attempt_allowed",
    "secret_resolution_allowed",
    "dispatcher_invocation_allowed",
    "workflow_execution_allowed",
    "payload_body_allowed",
    "persistence_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
)

_UNSAFE_RESULT_FLAGS: Final[tuple[str, ...]] = (
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


def normalize_connector_sandbox_read_fault_profile_id(
    fault_profile_id: str,
) -> str:
    return _validate_reference(
        "fault_profile_id",
        fault_profile_id,
    )


_KIND_TO_RESULT_STATUS: Final[
    MappingProxyType[
        ConnectorSandboxReadFaultKind,
        ConnectorSandboxReadFaultResultStatus,
    ]
] = MappingProxyType(
    {
        ConnectorSandboxReadFaultKind.SYNTHETIC_TIMEOUT: (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_TIMEOUT
        ),
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_TRANSPORT_UNAVAILABLE
        ): (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_TRANSPORT_UNAVAILABLE
        ),
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_AUTHORIZATION_DENIED
        ): (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_AUTHORIZATION_DENIED
        ),
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE
        ): (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE
        ),
        ConnectorSandboxReadFaultKind.SYNTHETIC_PLAN_REJECTED: (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_PLAN_REJECTED
        ),
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_OPERATOR_APPROVAL_MISSING
        ): (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_OPERATOR_APPROVAL_MISSING
        ),
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_SECURITY_REVIEW_MISSING
        ): (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_SECURITY_REVIEW_MISSING
        ),
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_MALFORMED_REFERENCE
        ): (
            ConnectorSandboxReadFaultResultStatus
            .SYNTHETIC_MALFORMED_REFERENCE
        ),
        ConnectorSandboxReadFaultKind.SAFE_REFUSAL: (
            ConnectorSandboxReadFaultResultStatus.SAFE_REFUSAL
        ),
    }
)


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadFaultProfile:
    fault_profile_id: str
    workflow_id: str
    kind: ConnectorSandboxReadFaultKind
    result_status: ConnectorSandboxReadFaultResultStatus
    reason_code: str
    reason_reference: str
    synthetic_fault_reference: str
    local_only: bool = True
    sandbox_only: bool = True
    read_only: bool = True
    deterministic: bool = True
    immediate_result: bool = True
    synthetic_reference_only: bool = True
    safe_refusal_required: bool = True
    status: ConnectorSandboxReadFaultProfileStatus = (
        ConnectorSandboxReadFaultProfileStatus.LOCAL_FAULT_READY
    )
    real_timeout_wait_allowed: bool = False
    retry_execution_allowed: bool = False
    automatic_retry_allowed: bool = False
    background_retry_allowed: bool = False
    network_attempt_allowed: bool = False
    secret_resolution_allowed: bool = False
    dispatcher_invocation_allowed: bool = False
    workflow_execution_allowed: bool = False
    payload_body_allowed: bool = False
    persistence_allowed: bool = False
    route_exposure_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        for name in (
            "fault_profile_id",
            "workflow_id",
            "reason_code",
            "reason_reference",
            "synthetic_fault_reference",
        ):
            _validate_reference(name, getattr(self, name))

        if self.workflow_id != _WORKFLOW_ID:
            raise ValueError(
                "fault profile must reference the governed R5 workflow."
            )

        if not isinstance(
            self.kind,
            ConnectorSandboxReadFaultKind,
        ):
            raise TypeError(
                "kind must be ConnectorSandboxReadFaultKind."
            )

        if not isinstance(
            self.result_status,
            ConnectorSandboxReadFaultResultStatus,
        ):
            raise TypeError(
                "result_status must be "
                "ConnectorSandboxReadFaultResultStatus."
            )

        if not isinstance(
            self.status,
            ConnectorSandboxReadFaultProfileStatus,
        ):
            raise TypeError(
                "status must be "
                "ConnectorSandboxReadFaultProfileStatus."
            )

        expected_status = _KIND_TO_RESULT_STATUS[self.kind]

        if self.result_status is not expected_status:
            raise ValueError(
                "fault kind and result status must match."
            )

        for name in _REQUIRED_TRUE_FLAGS:
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_PROFILE_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadFaultAssessment:
    fault_profile_id: str
    workflow_id: str
    status: ConnectorSandboxReadFaultProfileStatus
    contract_valid: bool
    workflow_valid: bool
    fault_injection_available: bool
    deterministic: bool
    immediate_result: bool
    synthetic_reference_only: bool
    safe_refusal_required: bool
    real_timeout_wait_allowed: bool
    retry_execution_allowed: bool
    automatic_retry_allowed: bool
    background_retry_allowed: bool
    network_attempt_allowed: bool
    secret_resolution_allowed: bool
    dispatcher_invocation_allowed: bool
    workflow_execution_allowed: bool
    payload_body_allowed: bool
    persistence_allowed: bool
    route_exposure_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadFaultRequest:
    request_id: str
    fault_profile_id: str
    workflow_request: ConnectorSandboxReadWorkflowRequest

    def __post_init__(self) -> None:
        _validate_reference("request_id", self.request_id)
        _validate_reference(
            "fault_profile_id",
            self.fault_profile_id,
        )

        if not isinstance(
            self.workflow_request,
            ConnectorSandboxReadWorkflowRequest,
        ):
            raise TypeError(
                "workflow_request must be "
                "ConnectorSandboxReadWorkflowRequest."
            )


@dataclass(frozen=True, slots=True)
class ConnectorSandboxReadFaultResult:
    request_id: str
    fault_profile_id: str
    workflow_id: str
    status: ConnectorSandboxReadFaultResultStatus
    reason_code: str
    reason_reference: str
    synthetic_fault_reference: str
    contract_validated: bool
    request_validated: bool
    workflow_validated: bool
    fault_injected: bool
    deterministic: bool
    immediate_result: bool
    safe_refusal: bool
    real_timeout_waited: bool = False
    retry_executed: bool = False
    automatic_retry_executed: bool = False
    background_retry_created: bool = False
    network_attempted: bool = False
    secret_resolved: bool = False
    dispatcher_invoked: bool = False
    workflow_executed: bool = False
    payload_body_used: bool = False
    payload_persisted: bool = False
    route_exposed: bool = False
    runtime_used: bool = False
    production_used: bool = False

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "fault_profile_id",
            "workflow_id",
            "reason_code",
            "reason_reference",
            "synthetic_fault_reference",
        ):
            _validate_reference(name, getattr(self, name))

        if not isinstance(
            self.status,
            ConnectorSandboxReadFaultResultStatus,
        ):
            raise TypeError(
                "status must be "
                "ConnectorSandboxReadFaultResultStatus."
            )

        for name in _UNSAFE_RESULT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")

def _profile(
    suffix: str,
    kind: ConnectorSandboxReadFaultKind,
    reason_code: str,
) -> ConnectorSandboxReadFaultProfile:
    return ConnectorSandboxReadFaultProfile(
        fault_profile_id=(
            f"telecom_ticketing_{suffix}_fault_profile"
        ),
        workflow_id=_WORKFLOW_ID,
        kind=kind,
        result_status=_KIND_TO_RESULT_STATUS[kind],
        reason_code=reason_code,
        reason_reference=f"{suffix}_reason_reference",
        synthetic_fault_reference=(
            f"{suffix}_fault_reference"
        ),
    )


_DECLARED_PROFILES: Final[
    tuple[ConnectorSandboxReadFaultProfile, ...]
] = (
    _profile(
        "synthetic_timeout",
        ConnectorSandboxReadFaultKind.SYNTHETIC_TIMEOUT,
        "synthetic_sandbox_read_timeout",
    ),
    _profile(
        "synthetic_transport_unavailable",
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_TRANSPORT_UNAVAILABLE
        ),
        "synthetic_sandbox_transport_unavailable",
    ),
    _profile(
        "synthetic_authorization_denied",
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_AUTHORIZATION_DENIED
        ),
        "synthetic_sandbox_authorization_denied",
    ),
    _profile(
        "synthetic_secret_reference_unavailable",
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_SECRET_REFERENCE_UNAVAILABLE
        ),
        "synthetic_secret_reference_unavailable",
    ),
    _profile(
        "synthetic_plan_rejected",
        ConnectorSandboxReadFaultKind.SYNTHETIC_PLAN_REJECTED,
        "synthetic_operation_plan_rejected",
    ),
    _profile(
        "synthetic_operator_approval_missing",
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_OPERATOR_APPROVAL_MISSING
        ),
        "synthetic_operator_approval_missing",
    ),
    _profile(
        "synthetic_security_review_missing",
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_SECURITY_REVIEW_MISSING
        ),
        "synthetic_security_review_missing",
    ),
    _profile(
        "synthetic_malformed_reference",
        (
            ConnectorSandboxReadFaultKind
            .SYNTHETIC_MALFORMED_REFERENCE
        ),
        "synthetic_malformed_reference_detected",
    ),
    _profile(
        "safe_refusal",
        ConnectorSandboxReadFaultKind.SAFE_REFUSAL,
        "sandbox_read_safely_refused",
    ),
)

CONNECTOR_SANDBOX_READ_FAULT_PROFILES = MappingProxyType(
    {
        profile.fault_profile_id: profile
        for profile in _DECLARED_PROFILES
    }
)

SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES = tuple(
    CONNECTOR_SANDBOX_READ_FAULT_PROFILES
)


def list_connector_sandbox_read_fault_profiles(
) -> tuple[ConnectorSandboxReadFaultProfile, ...]:
    return tuple(
        CONNECTOR_SANDBOX_READ_FAULT_PROFILES.values()
    )


def get_connector_sandbox_read_fault_profile(
    fault_profile_id: str,
) -> ConnectorSandboxReadFaultProfile:
    normalized = (
        normalize_connector_sandbox_read_fault_profile_id(
            fault_profile_id
        )
    )

    try:
        return CONNECTOR_SANDBOX_READ_FAULT_PROFILES[
            normalized
        ]
    except KeyError as exc:
        raise KeyError(
            f"unknown connector sandbox-read fault profile: "
            f"{normalized}"
        ) from exc


def _profile_validation_issues(
    profile: ConnectorSandboxReadFaultProfile,
) -> tuple[str, ...]:
    issues: list[str] = []

    if not isinstance(
        profile,
        ConnectorSandboxReadFaultProfile,
    ):
        return ("invalid_fault_profile_type",)

    if profile.workflow_id != _WORKFLOW_ID:
        issues.append("workflow_reference_mismatch")

    if profile.status is not (
        ConnectorSandboxReadFaultProfileStatus
        .LOCAL_FAULT_READY
    ):
        issues.append("fault_profile_not_ready")

    if (
        _KIND_TO_RESULT_STATUS.get(profile.kind)
        is not profile.result_status
    ):
        issues.append("fault_result_status_mismatch")

    for name in _REQUIRED_TRUE_FLAGS:
        if getattr(profile, name) is not True:
            issues.append(f"{name}_required")

    for name in _UNSAFE_PROFILE_FLAGS:
        if getattr(profile, name) is not False:
            issues.append(f"{name}_must_remain_disabled")

    try:
        workflow = get_connector_sandbox_read_workflow_contract(
            profile.workflow_id
        )
    except KeyError:
        issues.append("unknown_workflow_reference")
    else:
        if workflow.local_only is not True:
            issues.append("workflow_not_local_only")

        if workflow.sandbox_only is not True:
            issues.append("workflow_not_sandbox_only")

        if workflow.read_only is not True:
            issues.append("workflow_not_read_only")

        if workflow.external_http_allowed is not False:
            issues.append("workflow_network_not_disabled")

        if workflow.runtime_enabled is not False:
            issues.append("workflow_runtime_not_disabled")

        if workflow.production_allowed is not False:
            issues.append("workflow_production_not_disabled")

    return tuple(issues)


def validate_connector_sandbox_read_fault_profiles(
    profiles: Iterable[ConnectorSandboxReadFaultProfile],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()
    seen_kinds: set[ConnectorSandboxReadFaultKind] = set()

    for index, profile in enumerate(profiles):
        if not isinstance(
            profile,
            ConnectorSandboxReadFaultProfile,
        ):
            issues.append(
                f"profile_{index}:invalid_fault_profile_type"
            )
            continue

        if profile.fault_profile_id in seen_ids:
            issues.append(
                f"{profile.fault_profile_id}:duplicate_profile_id"
            )

        if profile.kind in seen_kinds:
            issues.append(
                f"{profile.fault_profile_id}:duplicate_fault_kind"
            )

        seen_ids.add(profile.fault_profile_id)
        seen_kinds.add(profile.kind)

        for issue in _profile_validation_issues(profile):
            issues.append(
                f"{profile.fault_profile_id}:{issue}"
            )

    expected_kinds = set(ConnectorSandboxReadFaultKind)

    if seen_kinds != expected_kinds:
        issues.append("fault_kind_coverage_incomplete")

    return tuple(issues)


def validate_connector_sandbox_read_fault_registry(
) -> tuple[str, ...]:
    issues = list(
        validate_connector_sandbox_read_fault_profiles(
            list_connector_sandbox_read_fault_profiles()
        )
    )

    if tuple(
        CONNECTOR_SANDBOX_READ_FAULT_PROFILES
    ) != SUPPORTED_CONNECTOR_SANDBOX_READ_FAULT_PROFILES:
        issues.append("supported_profile_order_mismatch")

    for key, profile in (
        CONNECTOR_SANDBOX_READ_FAULT_PROFILES.items()
    ):
        if key != profile.fault_profile_id:
            issues.append(f"{key}:registry_key_mismatch")

    return tuple(issues)


def assess_connector_sandbox_read_fault_profile(
    fault_profile_id: str,
) -> ConnectorSandboxReadFaultAssessment:
    profile = get_connector_sandbox_read_fault_profile(
        fault_profile_id
    )
    profile_issues = _profile_validation_issues(profile)

    try:
        workflow_assessment = (
            assess_connector_sandbox_read_workflow(
                profile.workflow_id
            )
        )
    except KeyError:
        workflow_valid = False
    else:
        workflow_valid = (
            workflow_assessment.contract_valid is True
            and workflow_assessment.reference_graph_valid is True
            and workflow_assessment.local_happy_path_available
            is True
            and workflow_assessment.deterministic is True
            and workflow_assessment.synthetic_reference_only
            is True
            and workflow_assessment.no_network is True
            and workflow_assessment.runtime_enabled is False
            and workflow_assessment.production_allowed is False
        )

    contract_valid = not profile_issues
    ready = contract_valid and workflow_valid

    blockers = [
        "real_timeout_wait_disabled",
        "retry_execution_disabled",
        "automatic_retry_disabled",
        "background_retry_disabled",
        "network_attempt_disabled",
        "secret_resolution_disabled",
        "dispatcher_invocation_disabled",
        "workflow_execution_disabled",
        "payload_body_disabled",
        "persistence_disabled",
        "route_exposure_disabled",
        "runtime_disabled",
        "production_disabled",
    ]

    blockers.extend(profile_issues)

    if not workflow_valid:
        blockers.append("governed_workflow_invalid")

    return ConnectorSandboxReadFaultAssessment(
        fault_profile_id=profile.fault_profile_id,
        workflow_id=profile.workflow_id,
        status=(
            ConnectorSandboxReadFaultProfileStatus
            .LOCAL_FAULT_READY
            if ready
            else ConnectorSandboxReadFaultProfileStatus.BLOCKED
        ),
        contract_valid=contract_valid,
        workflow_valid=workflow_valid,
        fault_injection_available=ready,
        deterministic=profile.deterministic,
        immediate_result=profile.immediate_result,
        synthetic_reference_only=(
            profile.synthetic_reference_only
        ),
        safe_refusal_required=profile.safe_refusal_required,
        real_timeout_wait_allowed=(
            profile.real_timeout_wait_allowed
        ),
        retry_execution_allowed=(
            profile.retry_execution_allowed
        ),
        automatic_retry_allowed=(
            profile.automatic_retry_allowed
        ),
        background_retry_allowed=(
            profile.background_retry_allowed
        ),
        network_attempt_allowed=profile.network_attempt_allowed,
        secret_resolution_allowed=(
            profile.secret_resolution_allowed
        ),
        dispatcher_invocation_allowed=(
            profile.dispatcher_invocation_allowed
        ),
        workflow_execution_allowed=(
            profile.workflow_execution_allowed
        ),
        payload_body_allowed=profile.payload_body_allowed,
        persistence_allowed=profile.persistence_allowed,
        route_exposure_allowed=profile.route_exposure_allowed,
        runtime_enabled=profile.runtime_enabled,
        production_allowed=profile.production_allowed,
        blocker_codes=tuple(blockers),
    )


def _workflow_request_is_valid(
    request: ConnectorSandboxReadFaultRequest,
    profile: ConnectorSandboxReadFaultProfile,
) -> bool:
    workflow_request = request.workflow_request

    if workflow_request.workflow_id != profile.workflow_id:
        return False

    try:
        workflow = get_connector_sandbox_read_workflow_contract(
            workflow_request.workflow_id
        )
    except KeyError:
        return False

    fake_request = workflow_request.fake_request
    transport_request = fake_request.transport_request
    dispatch_request = transport_request.dispatch_request

    if fake_request.fake_transport_id != workflow.fake_transport_id:
        return False

    if transport_request.transport_id != workflow.base_transport_id:
        return False

    if dispatch_request.plan_id != workflow.plan_id:
        return False

    if dispatch_request.simulation_mode is not True:
        return False

    for name in (
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
                name,
                getattr(dispatch_request, name),
            )
        except (TypeError, ValueError):
            return False

    return True


def _build_result(
    request: ConnectorSandboxReadFaultRequest,
    *,
    status: ConnectorSandboxReadFaultResultStatus,
    reason_code: str,
    reason_reference: str,
    synthetic_fault_reference: str,
    contract_validated: bool,
    request_validated: bool,
    workflow_validated: bool,
    fault_injected: bool,
) -> ConnectorSandboxReadFaultResult:
    return ConnectorSandboxReadFaultResult(
        request_id=request.request_id,
        fault_profile_id=request.fault_profile_id,
        workflow_id=request.workflow_request.workflow_id,
        status=status,
        reason_code=reason_code,
        reason_reference=reason_reference,
        synthetic_fault_reference=synthetic_fault_reference,
        contract_validated=contract_validated,
        request_validated=request_validated,
        workflow_validated=workflow_validated,
        fault_injected=fault_injected,
        deterministic=True,
        immediate_result=True,
        safe_refusal=True,
    )


class ConnectorDeterministicSandboxReadFaultSimulator:
    def simulate(
        self,
        request: ConnectorSandboxReadFaultRequest,
    ) -> ConnectorSandboxReadFaultResult:
        if not isinstance(
            request,
            ConnectorSandboxReadFaultRequest,
        ):
            raise TypeError(
                "request must be "
                "ConnectorSandboxReadFaultRequest."
            )

        try:
            profile = (
                get_connector_sandbox_read_fault_profile(
                    request.fault_profile_id
                )
            )
        except KeyError:
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadFaultResultStatus
                    .UNKNOWN_FAULT_PROFILE
                ),
                reason_code="unknown_sandbox_read_fault_profile",
                reason_reference=(
                    "unknown_fault_profile_reason_reference"
                ),
                synthetic_fault_reference=(
                    "synthetic_fault_unavailable_reference"
                ),
                contract_validated=False,
                request_validated=True,
                workflow_validated=False,
                fault_injected=False,
            )

        if not _workflow_request_is_valid(request, profile):
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadFaultResultStatus
                    .INVALID_REQUEST
                ),
                reason_code="invalid_sandbox_read_fault_request",
                reason_reference=(
                    "invalid_fault_request_reason_reference"
                ),
                synthetic_fault_reference=(
                    "synthetic_fault_unavailable_reference"
                ),
                contract_validated=True,
                request_validated=False,
                workflow_validated=False,
                fault_injected=False,
            )

        assessment = (
            assess_connector_sandbox_read_fault_profile(
                profile.fault_profile_id
            )
        )

        if (
            assessment.contract_valid is not True
            or assessment.workflow_valid is not True
            or assessment.fault_injection_available is not True
        ):
            return _build_result(
                request,
                status=(
                    ConnectorSandboxReadFaultResultStatus
                    .CONTRACT_BLOCKED
                ),
                reason_code="sandbox_read_fault_contract_blocked",
                reason_reference=(
                    "fault_contract_blocked_reason_reference"
                ),
                synthetic_fault_reference=(
                    "synthetic_fault_unavailable_reference"
                ),
                contract_validated=False,
                request_validated=True,
                workflow_validated=False,
                fault_injected=False,
            )

        return _build_result(
            request,
            status=profile.result_status,
            reason_code=profile.reason_code,
            reason_reference=profile.reason_reference,
            synthetic_fault_reference=(
                profile.synthetic_fault_reference
            ),
            contract_validated=True,
            request_validated=True,
            workflow_validated=True,
            fault_injected=True,
        )


def execute_connector_sandbox_read_fault(
    request: ConnectorSandboxReadFaultRequest,
) -> ConnectorSandboxReadFaultResult:
    return ConnectorDeterministicSandboxReadFaultSimulator().simulate(
        request
    )
