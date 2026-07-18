"""Disabled outbound allowlist and TLS readiness contracts.

R3A accepts safe, reference-only network-policy metadata for review. It does
not resolve DNS, apply an allowlist, open a port, load a certificate, create a
TLS context, configure a proxy, authorize egress, open a socket, perform HTTP,
persist a submission, expose a route, enable runtime, or authorize production.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.operator_sandbox_intake import (
    get_operator_sandbox_intake_contract,
)

__all__ = [
    "OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS",
    "SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS",
    "OutboundAllowlistTlsReadinessAssessment",
    "OutboundAllowlistTlsReadinessContract",
    "OutboundAllowlistTlsReadinessStatus",
    "OutboundAllowlistTlsReferenceSubmission",
    "TlsMinimumVersion",
    "assess_outbound_allowlist_tls_readiness",
    "get_outbound_allowlist_tls_readiness_contract",
    "list_outbound_allowlist_tls_readiness_contracts",
    "normalize_outbound_allowlist_tls_readiness_id",
    "validate_outbound_allowlist_tls_readiness_contracts",
    "validate_outbound_allowlist_tls_readiness_registry",
]


class TlsMinimumVersion(StrEnum):
    PENDING_SELECTION = "pending_tls_minimum_version"
    TLS_1_2 = "tls_1_2"
    TLS_1_3 = "tls_1_3"


class OutboundAllowlistTlsReadinessStatus(StrEnum):
    PENDING_NETWORK_POLICY_REFERENCES = (
        "pending_network_policy_references"
    )
    REFERENCES_RECEIVED_FOR_REVIEW = (
        "network_policy_references_received_for_review"
    )
    BLOCKED = "blocked"


_READINESS_ID: Final[str] = (
    "telecom_ticketing_outbound_allowlist_tls_readiness"
)
_INTAKE_ID: Final[str] = (
    "telecom_ticketing_operator_sandbox_reference_intake"
)
_CONNECTOR_ID: Final[str] = "telecom_ticketing_reference"

_SUPPORTED_TLS_MINIMUM_VERSIONS: Final[
    tuple[TlsMinimumVersion, ...]
] = (
    TlsMinimumVersion.TLS_1_2,
    TlsMinimumVersion.TLS_1_3,
)

_REQUIRED_REFERENCE_NAMES: Final[tuple[str, ...]] = (
    "allowlist_reference",
    "host_reference",
    "dns_policy_reference",
    "port_policy_reference",
    "ca_policy_reference",
    "certificate_pinning_policy_reference",
    "proxy_policy_reference",
    "egress_authorization_reference",
    "security_review_reference",
    "operator_approval_reference",
    "kill_switch_reference",
)

_REQUIRED_TRUE_FLAGS: Final[tuple[str, ...]] = (
    "sandbox_only",
    "reference_only",
    "read_only",
    "allowlist_required",
    "tls_required",
    "egress_authorization_required",
    "security_review_required",
    "operator_approval_required",
    "kill_switch_required",
)

_UNSAFE_FLAGS: Final[tuple[str, ...]] = (
    "allowlist_applied",
    "dns_resolution_performed",
    "port_opened",
    "tls_context_created",
    "ca_bundle_loaded",
    "certificate_loaded",
    "certificate_pin_applied",
    "proxy_configured",
    "egress_authorized",
    "kill_switch_armed",
    "connection_attempted",
    "external_http_enabled",
    "socket_access_enabled",
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
    "client_secret=",
    "private_key=",
    "certificate=",
    "api_key=",
    "raw_value=",
    "raw_payload=",
    "authorization:",
    "proxy-authorization:",
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
        _validate_reference(f"{name}[{index}]", value)

    return values


def normalize_outbound_allowlist_tls_readiness_id(
    readiness_id: str,
) -> str:
    return _validate_reference("readiness_id", readiness_id)


@dataclass(frozen=True, slots=True)
class OutboundAllowlistTlsReadinessContract:
    readiness_id: str
    intake_id: str
    connector_id: str
    environment: str
    access_mode: str
    selected_tls_minimum_version: TlsMinimumVersion
    supported_tls_minimum_versions: tuple[TlsMinimumVersion, ...]
    required_references: tuple[str, ...]
    sandbox_only: bool = True
    reference_only: bool = True
    read_only: bool = True
    allowlist_required: bool = True
    tls_required: bool = True
    egress_authorization_required: bool = True
    security_review_required: bool = True
    operator_approval_required: bool = True
    kill_switch_required: bool = True
    status: OutboundAllowlistTlsReadinessStatus = (
        OutboundAllowlistTlsReadinessStatus
        .PENDING_NETWORK_POLICY_REFERENCES
    )
    allowlist_applied: bool = False
    dns_resolution_performed: bool = False
    port_opened: bool = False
    tls_context_created: bool = False
    ca_bundle_loaded: bool = False
    certificate_loaded: bool = False
    certificate_pin_applied: bool = False
    proxy_configured: bool = False
    egress_authorized: bool = False
    kill_switch_armed: bool = False
    connection_attempted: bool = False
    external_http_enabled: bool = False
    socket_access_enabled: bool = False
    persistence_allowed: bool = False
    background_task_allowed: bool = False
    route_exposure_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False

    def __post_init__(self) -> None:
        for name in (
            "readiness_id",
            "intake_id",
            "connector_id",
            "environment",
            "access_mode",
        ):
            _validate_reference(name, getattr(self, name))

        _validate_reference_tuple(
            "required_references",
            self.required_references,
        )

        if self.intake_id != _INTAKE_ID:
            raise ValueError(
                "readiness must reference the governed R1 intake."
            )

        if self.connector_id != _CONNECTOR_ID:
            raise ValueError(
                "readiness must reference the telecom ticketing connector."
            )

        if self.environment != "sandbox":
            raise ValueError(
                "outbound readiness must remain sandbox-only."
            )

        if self.access_mode != "read":
            raise ValueError(
                "outbound readiness must remain read-only."
            )

        if self.selected_tls_minimum_version is not (
            TlsMinimumVersion.PENDING_SELECTION
        ):
            raise ValueError(
                "declared TLS minimum version must remain pending."
            )

        if self.supported_tls_minimum_versions != (
            _SUPPORTED_TLS_MINIMUM_VERSIONS
        ):
            raise ValueError(
                "supported TLS minimum version order must remain fixed."
            )

        if self.required_references != _REQUIRED_REFERENCE_NAMES:
            raise ValueError(
                "required network-policy references must remain fixed."
            )

        if self.status is not (
            OutboundAllowlistTlsReadinessStatus
            .PENDING_NETWORK_POLICY_REFERENCES
        ):
            raise ValueError(
                "declared outbound readiness must remain pending."
            )

        for name in _REQUIRED_TRUE_FLAGS:
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


@dataclass(frozen=True, slots=True)
class OutboundAllowlistTlsReferenceSubmission:
    submission_id: str
    readiness_id: str
    tls_minimum_version: TlsMinimumVersion
    allowlist_reference: str
    host_reference: str
    dns_policy_reference: str
    port_policy_reference: str
    ca_policy_reference: str
    certificate_pinning_policy_reference: str
    proxy_policy_reference: str
    egress_authorization_reference: str
    security_review_reference: str
    operator_approval_reference: str
    kill_switch_reference: str

    def __post_init__(self) -> None:
        for name in (
            "submission_id",
            "readiness_id",
            *_REQUIRED_REFERENCE_NAMES,
        ):
            _validate_reference(name, getattr(self, name))

        if self.readiness_id != _READINESS_ID:
            raise ValueError(
                "submission must reference the declared readiness."
            )

        if not isinstance(
            self.tls_minimum_version,
            TlsMinimumVersion,
        ):
            raise TypeError(
                "tls_minimum_version must be TlsMinimumVersion."
            )

        if self.tls_minimum_version not in (
            _SUPPORTED_TLS_MINIMUM_VERSIONS
        ):
            raise ValueError(
                "a supported non-pending TLS minimum version is required."
            )


@dataclass(frozen=True, slots=True)
class OutboundAllowlistTlsReadinessAssessment:
    readiness_id: str
    intake_id: str
    connector_id: str
    status: OutboundAllowlistTlsReadinessStatus
    contract_valid: bool
    intake_reference_valid: bool
    submission_present: bool
    tls_minimum_version_selected: bool
    selected_tls_minimum_version_reference: str
    reference_count: int
    required_reference_count: int
    references_valid: bool
    ready_for_network_policy_review: bool
    allowlist_applied: bool
    dns_resolution_performed: bool
    port_opened: bool
    tls_context_created: bool
    ca_bundle_loaded: bool
    certificate_loaded: bool
    certificate_pin_applied: bool
    proxy_configured: bool
    egress_authorized: bool
    kill_switch_armed: bool
    connection_attempted: bool
    external_http_enabled: bool
    socket_access_enabled: bool
    persistence_allowed: bool
    background_task_allowed: bool
    route_exposure_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    automatic_activation_allowed: bool
    blocker_codes: tuple[str, ...]


_DECLARED_CONTRACT: Final[
    OutboundAllowlistTlsReadinessContract
] = OutboundAllowlistTlsReadinessContract(
    readiness_id=_READINESS_ID,
    intake_id=_INTAKE_ID,
    connector_id=_CONNECTOR_ID,
    environment="sandbox",
    access_mode="read",
    selected_tls_minimum_version=(
        TlsMinimumVersion.PENDING_SELECTION
    ),
    supported_tls_minimum_versions=(
        _SUPPORTED_TLS_MINIMUM_VERSIONS
    ),
    required_references=_REQUIRED_REFERENCE_NAMES,
)

OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS = MappingProxyType(
    {
        _DECLARED_CONTRACT.readiness_id: _DECLARED_CONTRACT,
    }
)

SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS = tuple(
    OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS
)


def list_outbound_allowlist_tls_readiness_contracts(
) -> tuple[OutboundAllowlistTlsReadinessContract, ...]:
    return tuple(
        OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS.values()
    )


def get_outbound_allowlist_tls_readiness_contract(
    readiness_id: str,
) -> OutboundAllowlistTlsReadinessContract:
    normalized = normalize_outbound_allowlist_tls_readiness_id(
        readiness_id
    )

    try:
        return OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS[
            normalized
        ]
    except KeyError as exc:
        raise KeyError(
            f"unknown outbound allowlist/TLS readiness: {normalized}"
        ) from exc


def _contract_validation_issues(
    contract: OutboundAllowlistTlsReadinessContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    if not isinstance(
        contract,
        OutboundAllowlistTlsReadinessContract,
    ):
        return ("invalid_outbound_readiness_type",)

    if contract.intake_id != _INTAKE_ID:
        issues.append("intake_reference_mismatch")

    try:
        intake = get_operator_sandbox_intake_contract(
            contract.intake_id
        )
    except KeyError:
        issues.append("unknown_intake_reference")
    else:
        if intake.environment != "sandbox":
            issues.append("intake_not_sandbox")
        if intake.access_mode != "read":
            issues.append("intake_not_read_only")
        if intake.external_http_enabled is not False:
            issues.append("intake_external_http_not_disabled")
        if intake.runtime_enabled is not False:
            issues.append("intake_runtime_not_disabled")
        if intake.production_allowed is not False:
            issues.append("intake_production_not_disabled")

    if contract.connector_id != _CONNECTOR_ID:
        issues.append("connector_reference_mismatch")

    if contract.environment != "sandbox":
        issues.append("environment_must_be_sandbox")

    if contract.access_mode != "read":
        issues.append("access_mode_must_be_read")

    if contract.selected_tls_minimum_version is not (
        TlsMinimumVersion.PENDING_SELECTION
    ):
        issues.append("tls_minimum_version_must_remain_pending")

    if contract.supported_tls_minimum_versions != (
        _SUPPORTED_TLS_MINIMUM_VERSIONS
    ):
        issues.append("supported_tls_version_contract_mismatch")

    if contract.required_references != _REQUIRED_REFERENCE_NAMES:
        issues.append("required_reference_contract_mismatch")

    for name in _REQUIRED_TRUE_FLAGS:
        if getattr(contract, name) is not True:
            issues.append(f"{name}_required")

    for name in _UNSAFE_FLAGS:
        if getattr(contract, name) is not False:
            issues.append(f"{name}_must_remain_disabled")

    return tuple(issues)


def validate_outbound_allowlist_tls_readiness_contracts(
    contracts: Iterable[OutboundAllowlistTlsReadinessContract],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, contract in enumerate(contracts):
        if not isinstance(
            contract,
            OutboundAllowlistTlsReadinessContract,
        ):
            issues.append(
                f"contract_{index}:invalid_outbound_readiness_type"
            )
            continue

        if contract.readiness_id in seen_ids:
            issues.append(
                f"{contract.readiness_id}:duplicate_readiness_id"
            )

        seen_ids.add(contract.readiness_id)

        for issue in _contract_validation_issues(contract):
            issues.append(f"{contract.readiness_id}:{issue}")

    if not seen_ids:
        issues.append("no_outbound_readiness_declared")

    return tuple(issues)


def validate_outbound_allowlist_tls_readiness_registry(
) -> tuple[str, ...]:
    issues = list(
        validate_outbound_allowlist_tls_readiness_contracts(
            list_outbound_allowlist_tls_readiness_contracts()
        )
    )

    if tuple(
        OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS
    ) != SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS:
        issues.append("supported_readiness_order_mismatch")

    for key, contract in (
        OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS.items()
    ):
        if key != contract.readiness_id:
            issues.append(f"{key}:registry_key_mismatch")

    return tuple(issues)


def _submission_references_are_valid(
    submission: OutboundAllowlistTlsReferenceSubmission,
) -> bool:
    try:
        for name in _REQUIRED_REFERENCE_NAMES:
            _validate_reference(name, getattr(submission, name))
    except (TypeError, ValueError, AttributeError):
        return False

    return True


def assess_outbound_allowlist_tls_readiness(
    readiness_id: str,
    submission: OutboundAllowlistTlsReferenceSubmission | None = None,
) -> OutboundAllowlistTlsReadinessAssessment:
    contract = get_outbound_allowlist_tls_readiness_contract(
        readiness_id
    )
    contract_issues = _contract_validation_issues(contract)
    contract_valid = not contract_issues
    intake_reference_valid = (
        "unknown_intake_reference" not in contract_issues
        and "intake_reference_mismatch" not in contract_issues
    )

    if submission is None:
        submission_present = False
        tls_selected = False
        selected_tls_reference = (
            TlsMinimumVersion.PENDING_SELECTION.value
        )
        reference_count = 0
        references_valid = False
        status = (
            OutboundAllowlistTlsReadinessStatus
            .PENDING_NETWORK_POLICY_REFERENCES
        )
    elif not isinstance(
        submission,
        OutboundAllowlistTlsReferenceSubmission,
    ):
        raise TypeError(
            "submission must be "
            "OutboundAllowlistTlsReferenceSubmission or None."
        )
    elif submission.readiness_id != contract.readiness_id:
        submission_present = True
        tls_selected = False
        selected_tls_reference = "tls_selection_blocked_reference"
        reference_count = 0
        references_valid = False
        status = OutboundAllowlistTlsReadinessStatus.BLOCKED
    else:
        submission_present = True
        tls_selected = (
            submission.tls_minimum_version
            in _SUPPORTED_TLS_MINIMUM_VERSIONS
        )
        selected_tls_reference = (
            submission.tls_minimum_version.value
            if isinstance(
                submission.tls_minimum_version,
                TlsMinimumVersion,
            )
            else "invalid_tls_minimum_version_reference"
        )
        references_valid = _submission_references_are_valid(
            submission
        )
        reference_count = (
            len(_REQUIRED_REFERENCE_NAMES)
            if references_valid
            else 0
        )
        status = (
            OutboundAllowlistTlsReadinessStatus
            .REFERENCES_RECEIVED_FOR_REVIEW
            if (
                contract_valid
                and intake_reference_valid
                and tls_selected
                and references_valid
            )
            else OutboundAllowlistTlsReadinessStatus.BLOCKED
        )

    ready = (
        contract_valid
        and intake_reference_valid
        and submission_present
        and tls_selected
        and references_valid
        and reference_count == len(_REQUIRED_REFERENCE_NAMES)
    )

    blockers = list(contract_issues)

    if not submission_present:
        blockers.append("tls_minimum_version_selection_pending")
        blockers.extend(
            f"{name}_pending"
            for name in _REQUIRED_REFERENCE_NAMES
        )

    if submission_present and not tls_selected:
        blockers.append("supported_tls_minimum_version_required")

    if submission_present and not references_valid:
        blockers.append("network_policy_references_invalid")

    blockers.extend(
        (
            "allowlist_application_disabled",
            "dns_resolution_disabled",
            "port_opening_disabled",
            "tls_context_creation_disabled",
            "ca_bundle_loading_disabled",
            "certificate_loading_disabled",
            "certificate_pinning_disabled",
            "proxy_configuration_disabled",
            "egress_authorization_execution_disabled",
            "kill_switch_arming_disabled",
            "connection_attempts_disabled",
            "external_http_disabled",
            "socket_access_disabled",
            "persistence_disabled",
            "background_tasks_disabled",
            "route_exposure_disabled",
            "runtime_disabled",
            "production_disabled",
            "automatic_activation_disabled",
        )
    )

    return OutboundAllowlistTlsReadinessAssessment(
        readiness_id=contract.readiness_id,
        intake_id=contract.intake_id,
        connector_id=contract.connector_id,
        status=status,
        contract_valid=contract_valid,
        intake_reference_valid=intake_reference_valid,
        submission_present=submission_present,
        tls_minimum_version_selected=tls_selected,
        selected_tls_minimum_version_reference=(
            selected_tls_reference
        ),
        reference_count=reference_count,
        required_reference_count=len(_REQUIRED_REFERENCE_NAMES),
        references_valid=references_valid,
        ready_for_network_policy_review=ready,
        allowlist_applied=False,
        dns_resolution_performed=False,
        port_opened=False,
        tls_context_created=False,
        ca_bundle_loaded=False,
        certificate_loaded=False,
        certificate_pin_applied=False,
        proxy_configured=False,
        egress_authorized=False,
        kill_switch_armed=False,
        connection_attempted=False,
        external_http_enabled=False,
        socket_access_enabled=False,
        persistence_allowed=False,
        background_task_allowed=False,
        route_exposure_allowed=False,
        runtime_enabled=False,
        production_allowed=False,
        automatic_activation_allowed=False,
        blocker_codes=tuple(blockers),
    )
