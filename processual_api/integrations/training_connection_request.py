"""Governed training connection request and customer input package.

16G-R1 models a realistic connection request for training. It creates safe,
reference-only customer instructions. It does not issue a key, create a task,
bind a provider, resolve credentials, invoke the fake transport, persist data,
open a network connection, expose a route, or authorize runtime or production.
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
from processual_api.integrations.outbound_allowlist_tls_readiness import (
    get_outbound_allowlist_tls_readiness_contract,
)
from processual_api.integrations.secret_provider_binding_readiness import (
    SecretProviderKind,
    get_secret_provider_binding_readiness_contract,
)

__all__ = [
    "SUPPORTED_TRAINING_CONNECTION_REQUESTS",
    "TRAINING_CONNECTION_REQUEST_CONTRACTS",
    "TrainingConnectionInputDomain",
    "TrainingConnectionRequestAssessment",
    "TrainingConnectionRequestContract",
    "TrainingConnectionRequestStatus",
    "TrainingCustomerInputItem",
    "TrainingCustomerInputPackage",
    "assess_training_connection_request",
    "build_training_customer_input_package",
    "get_training_connection_request_contract",
    "list_training_connection_request_contracts",
    "normalize_training_connection_request_id",
    "render_training_customer_input_request",
    "validate_training_connection_request_contracts",
    "validate_training_connection_request_registry",
]


class TrainingConnectionRequestStatus(StrEnum):
    DRAFT_REQUEST = "draft_training_connection_request"
    PACKAGE_READY_FOR_CUSTOMER = "input_package_ready_for_customer"
    BLOCKED = "blocked"


class TrainingConnectionInputDomain(StrEnum):
    SECRET_PROVIDER = "secret_provider"
    OUTBOUND_TLS = "outbound_allowlist_tls"


_REQUEST_ID: Final[str] = (
    "telecom_ticketing_training_connection_request"
)
_PACKAGE_ID: Final[str] = (
    "telecom_ticketing_training_customer_input_package"
)
_INTAKE_ID: Final[str] = (
    "telecom_ticketing_operator_sandbox_reference_intake"
)
_PROVIDER_READINESS_ID: Final[str] = (
    "telecom_ticketing_secret_provider_binding_readiness"
)
_OUTBOUND_READINESS_ID: Final[str] = (
    "telecom_ticketing_outbound_allowlist_tls_readiness"
)
_CONNECTOR_ID: Final[str] = "telecom_ticketing_reference"

_PROVIDER_INPUT_IDS: Final[tuple[str, ...]] = (
    "provider.selected_secret_provider",
    "provider.environment_reference",
    "provider.tenant_project_or_vault_reference",
    "provider.authentication_method_reference",
    "provider.provider_reference",
    "provider.secret_reference",
    "provider.rotation_policy_reference",
    "provider.revocation_policy_reference",
    "provider.customer_authorization_reference",
    "provider.operator_approval_reference",
    "provider.security_review_reference",
    "provider.sdk_dependency_authorization_reference",
    "provider.network_access_authorization_reference",
    "provider.sandbox_credential_issuance_reference",
    "provider.credential_revocation_test_plan_reference",
)

_OUTBOUND_INPUT_IDS: Final[tuple[str, ...]] = (
    "outbound.allowlist_reference",
    "outbound.host_reference",
    "outbound.dns_policy_reference",
    "outbound.port_policy_reference",
    "outbound.tls_minimum_version_selection",
    "outbound.ca_policy_reference",
    "outbound.certificate_pinning_policy_reference",
    "outbound.proxy_policy_reference",
    "outbound.egress_authorization_reference",
    "outbound.security_review_reference",
    "outbound.operator_approval_reference",
    "outbound.kill_switch_reference",
)

_REQUIRED_INPUT_IDS: Final[tuple[str, ...]] = (
    *_PROVIDER_INPUT_IDS,
    *_OUTBOUND_INPUT_IDS,
)

_PROHIBITED_MARKERS: Final[tuple[str, ...]] = (
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
    "api_key=",
    "raw_value=",
    "raw_payload=",
)

_UNSAFE_FLAGS: Final[tuple[str, ...]] = (
    "customer_submission_received",
    "customer_submission_persisted",
    "integration_task_created",
    "activation_permission_key_issued",
    "provider_binding_created",
    "credentials_resolved",
    "allowlist_applied",
    "tls_context_created",
    "connection_attempted",
    "fake_transport_invoked",
    "sandbox_launched",
    "evidence_bundle_created",
    "external_http_enabled",
    "socket_access_enabled",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
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

    if any(marker in lowered for marker in _PROHIBITED_MARKERS):
        raise ValueError(
            f"{name} must be reference metadata, not raw material."
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


def normalize_training_connection_request_id(
    request_id: str,
) -> str:
    return _validate_reference("request_id", request_id)


@dataclass(frozen=True, slots=True)
class TrainingCustomerInputItem:
    item_id: str
    domain: TrainingConnectionInputDomain
    prompt: str
    required: bool = True
    reference_only: bool = True
    raw_value_prohibited: bool = True

    def __post_init__(self) -> None:
        _validate_reference("item_id", self.item_id)
        _validate_reference("prompt", self.prompt)

        if not isinstance(
            self.domain,
            TrainingConnectionInputDomain,
        ):
            raise TypeError(
                "domain must be TrainingConnectionInputDomain."
            )

        for name in (
            "required",
            "reference_only",
            "raw_value_prohibited",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")


@dataclass(frozen=True, slots=True)
class TrainingConnectionRequestContract:
    request_id: str
    package_id: str
    intake_id: str
    provider_readiness_id: str
    outbound_readiness_id: str
    connector_id: str
    environment: str
    access_mode: str
    required_input_ids: tuple[str, ...]
    status: TrainingConnectionRequestStatus = (
        TrainingConnectionRequestStatus.DRAFT_REQUEST
    )
    training_only: bool = True
    reference_only: bool = True
    customer_action_required: bool = True
    supervisor_review_required: bool = True
    customer_submission_received: bool = False
    customer_submission_persisted: bool = False
    integration_task_created: bool = False
    activation_permission_key_issued: bool = False
    provider_binding_created: bool = False
    credentials_resolved: bool = False
    allowlist_applied: bool = False
    tls_context_created: bool = False
    connection_attempted: bool = False
    fake_transport_invoked: bool = False
    sandbox_launched: bool = False
    evidence_bundle_created: bool = False
    external_http_enabled: bool = False
    socket_access_enabled: bool = False
    route_exposure_allowed: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "package_id",
            "intake_id",
            "provider_readiness_id",
            "outbound_readiness_id",
            "connector_id",
            "environment",
            "access_mode",
        ):
            _validate_reference(name, getattr(self, name))

        _validate_reference_tuple(
            "required_input_ids",
            self.required_input_ids,
        )

        if self.package_id != _PACKAGE_ID:
            raise ValueError("package_id must remain governed.")
        if self.intake_id != _INTAKE_ID:
            raise ValueError("intake_id must reference R1.")
        if self.provider_readiness_id != _PROVIDER_READINESS_ID:
            raise ValueError("provider_readiness_id must reference R2A.")
        if self.outbound_readiness_id != _OUTBOUND_READINESS_ID:
            raise ValueError("outbound_readiness_id must reference R3A.")
        if self.connector_id != _CONNECTOR_ID:
            raise ValueError("connector_id must remain governed.")
        if self.environment != "sandbox":
            raise ValueError("environment must remain sandbox.")
        if self.access_mode != "read":
            raise ValueError("access_mode must remain read.")
        if self.required_input_ids != _REQUIRED_INPUT_IDS:
            raise ValueError("required input order must remain fixed.")
        if self.status is not TrainingConnectionRequestStatus.DRAFT_REQUEST:
            raise ValueError("declared request must remain draft.")

        for name in (
            "training_only",
            "reference_only",
            "customer_action_required",
            "supervisor_review_required",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


@dataclass(frozen=True, slots=True)
class TrainingCustomerInputPackage:
    package_id: str
    request_id: str
    status: TrainingConnectionRequestStatus
    subject: str
    recipient_role: str
    instructions: tuple[str, ...]
    provider_candidates: tuple[str, ...]
    tls_candidates: tuple[str, ...]
    items: tuple[TrainingCustomerInputItem, ...]
    input_count: int
    reference_only: bool
    raw_values_prohibited: bool
    ready_for_customer: bool
    activation_permission_key_issued: bool
    fake_transport_invoked: bool
    sandbox_launched: bool
    runtime_enabled: bool
    production_allowed: bool


@dataclass(frozen=True, slots=True)
class TrainingConnectionRequestAssessment:
    request_id: str
    status: TrainingConnectionRequestStatus
    contract_valid: bool
    dependencies_valid: bool
    required_input_count: int
    package_ready_for_customer: bool
    customer_submission_received: bool
    integration_task_created: bool
    activation_permission_key_issued: bool
    fake_transport_invoked: bool
    sandbox_launched: bool
    external_http_enabled: bool
    socket_access_enabled: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]


def _item(
    item_id: str,
    domain: TrainingConnectionInputDomain,
) -> TrainingCustomerInputItem:
    prompt = (
        f"Provide an approved reference for {item_id}; "
        "do not provide a raw value."
    )
    return TrainingCustomerInputItem(
        item_id=item_id,
        domain=domain,
        prompt=prompt,
    )


_INPUT_ITEMS: Final[tuple[TrainingCustomerInputItem, ...]] = (
    *tuple(
        _item(
            item_id,
            TrainingConnectionInputDomain.SECRET_PROVIDER,
        )
        for item_id in _PROVIDER_INPUT_IDS
    ),
    *tuple(
        _item(
            item_id,
            TrainingConnectionInputDomain.OUTBOUND_TLS,
        )
        for item_id in _OUTBOUND_INPUT_IDS
    ),
)

_DECLARED_CONTRACT: Final[
    TrainingConnectionRequestContract
] = TrainingConnectionRequestContract(
    request_id=_REQUEST_ID,
    package_id=_PACKAGE_ID,
    intake_id=_INTAKE_ID,
    provider_readiness_id=_PROVIDER_READINESS_ID,
    outbound_readiness_id=_OUTBOUND_READINESS_ID,
    connector_id=_CONNECTOR_ID,
    environment="sandbox",
    access_mode="read",
    required_input_ids=_REQUIRED_INPUT_IDS,
)

TRAINING_CONNECTION_REQUEST_CONTRACTS = MappingProxyType(
    {_DECLARED_CONTRACT.request_id: _DECLARED_CONTRACT}
)

SUPPORTED_TRAINING_CONNECTION_REQUESTS = tuple(
    TRAINING_CONNECTION_REQUEST_CONTRACTS
)


def list_training_connection_request_contracts(
) -> tuple[TrainingConnectionRequestContract, ...]:
    return tuple(TRAINING_CONNECTION_REQUEST_CONTRACTS.values())


def get_training_connection_request_contract(
    request_id: str,
) -> TrainingConnectionRequestContract:
    normalized = normalize_training_connection_request_id(request_id)

    try:
        return TRAINING_CONNECTION_REQUEST_CONTRACTS[normalized]
    except KeyError as exc:
        raise KeyError(
            f"unknown training connection request: {normalized}"
        ) from exc


def _contract_validation_issues(
    contract: TrainingConnectionRequestContract,
) -> tuple[str, ...]:
    if not isinstance(contract, TrainingConnectionRequestContract):
        return ("invalid_training_connection_request_type",)

    issues: list[str] = []

    dependency_specs = (
        (
            contract.intake_id,
            _INTAKE_ID,
            get_operator_sandbox_intake_contract,
            "intake",
        ),
        (
            contract.provider_readiness_id,
            _PROVIDER_READINESS_ID,
            get_secret_provider_binding_readiness_contract,
            "provider_readiness",
        ),
        (
            contract.outbound_readiness_id,
            _OUTBOUND_READINESS_ID,
            get_outbound_allowlist_tls_readiness_contract,
            "outbound_readiness",
        ),
    )

    for actual, expected, getter, label in dependency_specs:
        if actual != expected:
            issues.append(f"{label}_reference_mismatch")
            continue

        try:
            dependency = getter(actual)
        except KeyError:
            issues.append(f"unknown_{label}_reference")
            continue

        if dependency.environment != "sandbox":
            issues.append(f"{label}_not_sandbox")
        if getattr(dependency, "runtime_enabled", False) is not False:
            issues.append(f"{label}_runtime_not_disabled")
        if getattr(dependency, "production_allowed", False) is not False:
            issues.append(f"{label}_production_not_disabled")

    if contract.required_input_ids != _REQUIRED_INPUT_IDS:
        issues.append("required_input_contract_mismatch")

    for name in _UNSAFE_FLAGS:
        if getattr(contract, name) is not False:
            issues.append(f"{name}_must_remain_disabled")

    return tuple(issues)


def validate_training_connection_request_contracts(
    contracts: Iterable[TrainingConnectionRequestContract],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, contract in enumerate(contracts):
        if not isinstance(contract, TrainingConnectionRequestContract):
            issues.append(
                f"contract_{index}:invalid_training_connection_request_type"
            )
            continue

        if contract.request_id in seen_ids:
            issues.append(f"{contract.request_id}:duplicate_request_id")

        seen_ids.add(contract.request_id)

        for issue in _contract_validation_issues(contract):
            issues.append(f"{contract.request_id}:{issue}")

    if not seen_ids:
        issues.append("no_training_connection_request_declared")

    return tuple(issues)


def validate_training_connection_request_registry(
) -> tuple[str, ...]:
    issues = list(
        validate_training_connection_request_contracts(
            list_training_connection_request_contracts()
        )
    )

    if tuple(TRAINING_CONNECTION_REQUEST_CONTRACTS) != (
        SUPPORTED_TRAINING_CONNECTION_REQUESTS
    ):
        issues.append("supported_request_order_mismatch")

    return tuple(issues)


def assess_training_connection_request(
    request_id: str,
) -> TrainingConnectionRequestAssessment:
    contract = get_training_connection_request_contract(request_id)
    issues = _contract_validation_issues(contract)
    valid = not issues

    blockers = list(issues)
    blockers.extend(
        (
            "customer_submission_pending",
            "supervisor_review_pending",
            "integration_task_creation_disabled",
            "activation_permission_key_issuance_disabled",
            "provider_binding_disabled",
            "credential_resolution_disabled",
            "allowlist_application_disabled",
            "tls_context_creation_disabled",
            "connection_attempts_disabled",
            "fake_transport_invocation_disabled",
            "sandbox_launch_disabled",
            "evidence_creation_disabled",
            "external_http_disabled",
            "socket_access_disabled",
            "runtime_disabled",
            "production_disabled",
        )
    )

    return TrainingConnectionRequestAssessment(
        request_id=contract.request_id,
        status=(
            TrainingConnectionRequestStatus.PACKAGE_READY_FOR_CUSTOMER
            if valid
            else TrainingConnectionRequestStatus.BLOCKED
        ),
        contract_valid=valid,
        dependencies_valid=valid,
        required_input_count=len(_REQUIRED_INPUT_IDS),
        package_ready_for_customer=valid,
        customer_submission_received=False,
        integration_task_created=False,
        activation_permission_key_issued=False,
        fake_transport_invoked=False,
        sandbox_launched=False,
        external_http_enabled=False,
        socket_access_enabled=False,
        runtime_enabled=False,
        production_allowed=False,
        blocker_codes=tuple(blockers),
    )


def build_training_customer_input_package(
    request_id: str,
) -> TrainingCustomerInputPackage:
    assessment = assess_training_connection_request(request_id)

    if not assessment.package_ready_for_customer:
        raise ValueError(
            "training input package is blocked by invalid dependencies."
        )

    instructions = (
        "Return approved reference names only.",
        "Do not send passwords, tokens, keys, certificates, or raw secrets.",
        "Keep production endpoints and production credentials out of training.",
        "Each reference remains subject to supervisor and operator review.",
        "Completing this package does not authorize network or runtime access.",
    )

    provider_candidates = tuple(
        provider.value
        for provider in SecretProviderKind
        if provider is not SecretProviderKind.PENDING_SELECTION
    )

    return TrainingCustomerInputPackage(
        package_id=_PACKAGE_ID,
        request_id=_REQUEST_ID,
        status=TrainingConnectionRequestStatus.PACKAGE_READY_FOR_CUSTOMER,
        subject=(
            "Training request for governed sandbox connection inputs"
        ),
        recipient_role="customer_integration_officer",
        instructions=instructions,
        provider_candidates=provider_candidates,
        tls_candidates=("tls_1_2", "tls_1_3"),
        items=_INPUT_ITEMS,
        input_count=len(_INPUT_ITEMS),
        reference_only=True,
        raw_values_prohibited=True,
        ready_for_customer=True,
        activation_permission_key_issued=False,
        fake_transport_invoked=False,
        sandbox_launched=False,
        runtime_enabled=False,
        production_allowed=False,
    )


def render_training_customer_input_request(
    request_id: str,
) -> str:
    package = build_training_customer_input_package(request_id)
    lines = [
        package.subject,
        f"request_id: {package.request_id}",
        f"package_id: {package.package_id}",
        f"recipient_role: {package.recipient_role}",
        "",
        "Instructions:",
    ]

    lines.extend(f"- {value}" for value in package.instructions)
    lines.extend(("", "Required reference inputs:"))
    lines.extend(
        f"- [{item.domain.value}] {item.item_id}: {item.prompt}"
        for item in package.items
    )
    lines.extend(
        (
            "",
            "This training package does not issue an activation key.",
            "This training package does not launch a sandbox.",
            "runtime_enabled: false",
            "production_allowed: false",
        )
    )

    return "\n".join(lines) + "\n"
