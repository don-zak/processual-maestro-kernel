"""Governed review of synthetic training connection input packages.

16G-R2 validates reference-only customer training submissions and projects
them through the existing R2A and R3A readiness contracts. It does not persist
a submission, create a task, issue a key, bind a provider, resolve credentials,
invoke a transport, launch a sandbox, open a network, or authorize production.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from processual_api.integrations.outbound_allowlist_tls_readiness import (
    OutboundAllowlistTlsReferenceSubmission,
    TlsMinimumVersion,
    assess_outbound_allowlist_tls_readiness,
)
from processual_api.integrations.secret_provider_binding_readiness import (
    SecretProviderKind,
    SecretProviderReferenceSubmission,
    assess_secret_provider_binding_readiness,
)
from processual_api.integrations.training_connection_request import (
    build_training_customer_input_package,
)

__all__ = [
    "TrainingCustomerInputReview",
    "TrainingCustomerInputReviewStatus",
    "TrainingCustomerInputSubmission",
    "review_training_customer_input_submission",
]


class TrainingCustomerInputReviewStatus(StrEnum):
    NEEDS_CLARIFICATION = "needs_clarification"
    REJECTED_UNSAFE_INPUT = "rejected_unsafe_input"
    READY_FOR_SUPERVISOR_REVIEW = "ready_for_supervisor_review"
    BLOCKED = "blocked"


_REQUEST_ID = "telecom_ticketing_training_connection_request"
_PROVIDER_READINESS_ID = (
    "telecom_ticketing_secret_provider_binding_readiness"
)
_OUTBOUND_READINESS_ID = (
    "telecom_ticketing_outbound_allowlist_tls_readiness"
)

_PROHIBITED_MARKERS = (
    "http://",
    "https://",
    "://",
    "bearer ",
    "basic ",
    "password=",
    "token=",
    "secret=",
    "client_secret=",
    "private_key=",
    "certificate=",
    "api_key=",
    "raw_value=",
    "raw_payload=",
    "authorization:",
)

_UNSAFE_RESULT_FIELDS = (
    "customer_submission_persisted",
    "integration_task_created",
    "activation_permission_key_issued",
    "provider_binding_created",
    "credentials_resolved",
    "connection_attempted",
    "fake_transport_invoked",
    "sandbox_launched",
    "external_http_enabled",
    "socket_access_enabled",
    "runtime_enabled",
    "production_allowed",
)


def _safe_reference(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{name} must not be empty.")

    if normalized != value:
        raise ValueError(
            f"{name} must not contain surrounding whitespace."
        )

    lowered = normalized.lower()

    if any(marker in lowered for marker in _PROHIBITED_MARKERS):
        raise ValueError(
            f"{name} contains prohibited raw material."
        )

    return normalized


@dataclass(frozen=True, slots=True)
class TrainingCustomerInputSubmission:
    submission_id: str
    request_id: str
    values: Mapping[str, str]

    def __post_init__(self) -> None:
        _safe_reference("submission_id", self.submission_id)
        _safe_reference("request_id", self.request_id)

        if self.request_id != _REQUEST_ID:
            raise ValueError(
                "submission must reference the governed R1 request."
            )

        if not isinstance(self.values, Mapping):
            raise TypeError("values must be a mapping.")

        copied: dict[str, str] = {}

        for key, value in self.values.items():
            safe_key = _safe_reference("input key", key)
            copied[safe_key] = _safe_reference(safe_key, value)

        object.__setattr__(
            self,
            "values",
            MappingProxyType(copied),
        )


@dataclass(frozen=True, slots=True)
class TrainingCustomerInputReview:
    submission_id: str
    request_id: str
    status: TrainingCustomerInputReviewStatus
    expected_input_count: int
    received_input_count: int
    missing_input_ids: tuple[str, ...]
    unexpected_input_ids: tuple[str, ...]
    schema_valid: bool
    provider_submission_valid: bool
    outbound_submission_valid: bool
    ready_for_supervisor_review: bool
    customer_submission_persisted: bool
    integration_task_created: bool
    activation_permission_key_issued: bool
    provider_binding_created: bool
    credentials_resolved: bool
    connection_attempted: bool
    fake_transport_invoked: bool
    sandbox_launched: bool
    external_http_enabled: bool
    socket_access_enabled: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in _UNSAFE_RESULT_FIELDS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")
def _review_result(
    submission: TrainingCustomerInputSubmission,
    *,
    status: TrainingCustomerInputReviewStatus,
    expected_count: int,
    received_count: int,
    missing: tuple[str, ...],
    unexpected: tuple[str, ...],
    schema_valid: bool,
    provider_valid: bool = False,
    outbound_valid: bool = False,
    ready: bool = False,
    blockers: tuple[str, ...] = (),
) -> TrainingCustomerInputReview:
    return TrainingCustomerInputReview(
        submission_id=submission.submission_id,
        request_id=submission.request_id,
        status=status,
        expected_input_count=expected_count,
        received_input_count=received_count,
        missing_input_ids=missing,
        unexpected_input_ids=unexpected,
        schema_valid=schema_valid,
        provider_submission_valid=provider_valid,
        outbound_submission_valid=outbound_valid,
        ready_for_supervisor_review=ready,
        customer_submission_persisted=False,
        integration_task_created=False,
        activation_permission_key_issued=False,
        provider_binding_created=False,
        credentials_resolved=False,
        connection_attempted=False,
        fake_transport_invoked=False,
        sandbox_launched=False,
        external_http_enabled=False,
        socket_access_enabled=False,
        runtime_enabled=False,
        production_allowed=False,
        blocker_codes=blockers,
    )


def review_training_customer_input_submission(
    submission: TrainingCustomerInputSubmission,
) -> TrainingCustomerInputReview:
    if not isinstance(submission, TrainingCustomerInputSubmission):
        raise TypeError(
            "submission must be TrainingCustomerInputSubmission."
        )

    package = build_training_customer_input_package(
        submission.request_id
    )
    expected = tuple(item.item_id for item in package.items)
    expected_set = set(expected)
    received_set = set(submission.values)

    missing = tuple(
        item_id
        for item_id in expected
        if item_id not in received_set
    )
    unexpected = tuple(sorted(received_set - expected_set))

    if missing:
        return _review_result(
            submission,
            status=TrainingCustomerInputReviewStatus.NEEDS_CLARIFICATION,
            expected_count=len(expected),
            received_count=len(received_set),
            missing=missing,
            unexpected=unexpected,
            schema_valid=False,
            blockers=(
                *(f"{item_id}_missing" for item_id in missing),
                "customer_clarification_required",
                "activation_permission_key_issuance_disabled",
                "sandbox_launch_disabled",
                "production_disabled",
            ),
        )

    if unexpected:
        return _review_result(
            submission,
            status=TrainingCustomerInputReviewStatus.BLOCKED,
            expected_count=len(expected),
            received_count=len(received_set),
            missing=(),
            unexpected=unexpected,
            schema_valid=False,
            blockers=(
                *(f"{item_id}_unexpected" for item_id in unexpected),
                "submission_schema_blocked",
                "activation_permission_key_issuance_disabled",
                "sandbox_launch_disabled",
                "production_disabled",
            ),
        )

    values = submission.values

    try:
        provider_kind = SecretProviderKind(
            values["provider.selected_secret_provider"]
        )
        tls_version = TlsMinimumVersion(
            values["outbound.tls_minimum_version_selection"]
        )

        provider_submission = SecretProviderReferenceSubmission(
            submission_id=(
                f"{submission.submission_id}_provider"
            ),
            readiness_id=_PROVIDER_READINESS_ID,
            provider_kind=provider_kind,
            provider_reference=values[
                "provider.provider_reference"
            ],
            authentication_reference=values[
                "provider.authentication_method_reference"
            ],
            rotation_policy_reference=values[
                "provider.rotation_policy_reference"
            ],
            customer_authorization_reference=values[
                "provider.customer_authorization_reference"
            ],
            operator_approval_reference=values[
                "provider.operator_approval_reference"
            ],
            security_review_reference=values[
                "provider.security_review_reference"
            ],
            revocation_policy_reference=values[
                "provider.revocation_policy_reference"
            ],
        )

        outbound_submission = OutboundAllowlistTlsReferenceSubmission(
            submission_id=(
                f"{submission.submission_id}_outbound"
            ),
            readiness_id=_OUTBOUND_READINESS_ID,
            tls_minimum_version=tls_version,
            allowlist_reference=values[
                "outbound.allowlist_reference"
            ],
            host_reference=values["outbound.host_reference"],
            dns_policy_reference=values[
                "outbound.dns_policy_reference"
            ],
            port_policy_reference=values[
                "outbound.port_policy_reference"
            ],
            ca_policy_reference=values[
                "outbound.ca_policy_reference"
            ],
            certificate_pinning_policy_reference=values[
                "outbound.certificate_pinning_policy_reference"
            ],
            proxy_policy_reference=values[
                "outbound.proxy_policy_reference"
            ],
            egress_authorization_reference=values[
                "outbound.egress_authorization_reference"
            ],
            security_review_reference=values[
                "outbound.security_review_reference"
            ],
            operator_approval_reference=values[
                "outbound.operator_approval_reference"
            ],
            kill_switch_reference=values[
                "outbound.kill_switch_reference"
            ],
        )

        provider_assessment = (
            assess_secret_provider_binding_readiness(
                _PROVIDER_READINESS_ID,
                provider_submission,
            )
        )
        outbound_assessment = (
            assess_outbound_allowlist_tls_readiness(
                _OUTBOUND_READINESS_ID,
                outbound_submission,
            )
        )
    except (KeyError, TypeError, ValueError):
        return _review_result(
            submission,
            status=(
                TrainingCustomerInputReviewStatus
                .REJECTED_UNSAFE_INPUT
            ),
            expected_count=len(expected),
            received_count=len(received_set),
            missing=(),
            unexpected=(),
            schema_valid=False,
            blockers=(
                "reference_submission_rejected",
                "activation_permission_key_issuance_disabled",
                "sandbox_launch_disabled",
                "production_disabled",
            ),
        )

    provider_valid = (
        provider_assessment.ready_for_provider_review
    )
    outbound_valid = (
        outbound_assessment.ready_for_network_policy_review
    )
    ready = provider_valid and outbound_valid

    return _review_result(
        submission,
        status=(
            TrainingCustomerInputReviewStatus
            .READY_FOR_SUPERVISOR_REVIEW
            if ready
            else TrainingCustomerInputReviewStatus.BLOCKED
        ),
        expected_count=len(expected),
        received_count=len(received_set),
        missing=(),
        unexpected=(),
        schema_valid=True,
        provider_valid=provider_valid,
        outbound_valid=outbound_valid,
        ready=ready,
        blockers=(
            "supervisor_review_required",
            "integration_task_creation_disabled",
            "activation_permission_key_issuance_disabled",
            "provider_binding_disabled",
            "connection_attempts_disabled",
            "fake_transport_invocation_disabled",
            "sandbox_launch_disabled",
            "runtime_disabled",
            "production_disabled",
        ),
    )
