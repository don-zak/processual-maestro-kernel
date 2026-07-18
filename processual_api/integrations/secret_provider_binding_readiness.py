"""Disabled secret-provider binding readiness contracts.

R2A declares candidate provider kinds and accepts safe reference names for
review. It does not bind a provider, register or resolve a secret, read a
vault, authenticate, open a network connection, persist a submission, expose
a route, enable runtime execution, or authorize production.
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
    "SECRET_PROVIDER_BINDING_READINESS_CONTRACTS",
    "SUPPORTED_SECRET_PROVIDER_BINDING_READINESS",
    "SecretProviderBindingReadinessAssessment",
    "SecretProviderBindingReadinessContract",
    "SecretProviderBindingReadinessStatus",
    "SecretProviderKind",
    "SecretProviderReferenceSubmission",
    "assess_secret_provider_binding_readiness",
    "get_secret_provider_binding_readiness_contract",
    "list_secret_provider_binding_readiness_contracts",
    "normalize_secret_provider_binding_readiness_id",
    "validate_secret_provider_binding_readiness_contracts",
    "validate_secret_provider_binding_readiness_registry",
]


class SecretProviderKind(StrEnum):
    PENDING_SELECTION = "pending_provider_selection"
    GCP_SECRET_MANAGER = "gcp_secret_manager"
    HASHICORP_VAULT = "hashicorp_vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    AZURE_KEY_VAULT = "azure_key_vault"


class SecretProviderBindingReadinessStatus(StrEnum):
    PENDING_PROVIDER_REFERENCE = "pending_provider_reference"
    REFERENCES_RECEIVED_FOR_REVIEW = (
        "provider_references_received_for_review"
    )
    BLOCKED = "blocked"


_READINESS_ID: Final[str] = (
    "telecom_ticketing_secret_provider_binding_readiness"
)
_INTAKE_ID: Final[str] = (
    "telecom_ticketing_operator_sandbox_reference_intake"
)
_SECRET_MANAGER_CONTRACT_ID: Final[str] = (
    "telecom_operations_customer_vault_secret_manager_contract"
)
_CREDENTIAL_PROFILE_ID: Final[str] = (
    "telecom_operations_api_reference"
)

_CANDIDATE_PROVIDERS: Final[tuple[SecretProviderKind, ...]] = (
    SecretProviderKind.GCP_SECRET_MANAGER,
    SecretProviderKind.HASHICORP_VAULT,
    SecretProviderKind.AWS_SECRETS_MANAGER,
    SecretProviderKind.AZURE_KEY_VAULT,
)

_REQUIRED_REFERENCE_NAMES: Final[tuple[str, ...]] = (
    "provider_reference",
    "authentication_reference",
    "rotation_policy_reference",
    "customer_authorization_reference",
    "operator_approval_reference",
    "security_review_reference",
    "revocation_policy_reference",
)

_REQUIRED_TRUE_FLAGS: Final[tuple[str, ...]] = (
    "sandbox_only",
    "reference_only",
    "customer_supplied",
    "customer_authorization_required",
    "operator_approval_required",
    "security_review_required",
    "rotation_policy_required",
    "revocation_policy_required",
)

_UNSAFE_FLAGS: Final[tuple[str, ...]] = (
    "provider_binding_created",
    "provider_client_initialized",
    "secret_reference_registered",
    "secret_value_accessed",
    "secret_value_stored",
    "raw_secret_visible",
    "authentication_performed",
    "credentials_resolved",
    "resolution_allowed",
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
    "service_account=",
    "api_key=",
    "raw_value=",
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


def normalize_secret_provider_binding_readiness_id(
    readiness_id: str,
) -> str:
    return _validate_reference("readiness_id", readiness_id)


@dataclass(frozen=True, slots=True)
class SecretProviderBindingReadinessContract:
    readiness_id: str
    intake_id: str
    secret_manager_contract_id: str
    credential_profile_id: str
    environment: str
    selected_provider: SecretProviderKind
    candidate_providers: tuple[SecretProviderKind, ...]
    required_references: tuple[str, ...]
    sandbox_only: bool = True
    reference_only: bool = True
    customer_supplied: bool = True
    customer_authorization_required: bool = True
    operator_approval_required: bool = True
    security_review_required: bool = True
    rotation_policy_required: bool = True
    revocation_policy_required: bool = True
    status: SecretProviderBindingReadinessStatus = (
        SecretProviderBindingReadinessStatus
        .PENDING_PROVIDER_REFERENCE
    )
    provider_binding_created: bool = False
    provider_client_initialized: bool = False
    secret_reference_registered: bool = False
    secret_value_accessed: bool = False
    secret_value_stored: bool = False
    raw_secret_visible: bool = False
    authentication_performed: bool = False
    credentials_resolved: bool = False
    resolution_allowed: bool = False
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
            "secret_manager_contract_id",
            "credential_profile_id",
            "environment",
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

        if self.environment != "sandbox":
            raise ValueError(
                "provider readiness must remain sandbox-only."
            )

        if self.selected_provider is not (
            SecretProviderKind.PENDING_SELECTION
        ):
            raise ValueError(
                "declared readiness must remain pending selection."
            )

        if self.candidate_providers != _CANDIDATE_PROVIDERS:
            raise ValueError(
                "candidate provider order must remain fixed."
            )

        if self.required_references != _REQUIRED_REFERENCE_NAMES:
            raise ValueError(
                "required references must remain fixed."
            )

        if self.status is not (
            SecretProviderBindingReadinessStatus
            .PENDING_PROVIDER_REFERENCE
        ):
            raise ValueError(
                "declared readiness must remain pending."
            )

        for name in _REQUIRED_TRUE_FLAGS:
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must remain true.")

        for name in _UNSAFE_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


@dataclass(frozen=True, slots=True)
class SecretProviderReferenceSubmission:
    submission_id: str
    readiness_id: str
    provider_kind: SecretProviderKind
    provider_reference: str
    authentication_reference: str
    rotation_policy_reference: str
    customer_authorization_reference: str
    operator_approval_reference: str
    security_review_reference: str
    revocation_policy_reference: str

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
            self.provider_kind,
            SecretProviderKind,
        ):
            raise TypeError(
                "provider_kind must be SecretProviderKind."
            )

        if self.provider_kind not in _CANDIDATE_PROVIDERS:
            raise ValueError(
                "a supported non-pending provider must be selected."
            )


@dataclass(frozen=True, slots=True)
class SecretProviderBindingReadinessAssessment:
    readiness_id: str
    intake_id: str
    status: SecretProviderBindingReadinessStatus
    contract_valid: bool
    intake_reference_valid: bool
    submission_present: bool
    provider_selected: bool
    selected_provider_reference: str
    reference_count: int
    required_reference_count: int
    references_valid: bool
    ready_for_provider_review: bool
    provider_binding_created: bool
    provider_client_initialized: bool
    secret_reference_registered: bool
    secret_value_accessed: bool
    secret_value_stored: bool
    raw_secret_visible: bool
    authentication_performed: bool
    credentials_resolved: bool
    resolution_allowed: bool
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
    SecretProviderBindingReadinessContract
] = SecretProviderBindingReadinessContract(
    readiness_id=_READINESS_ID,
    intake_id=_INTAKE_ID,
    secret_manager_contract_id=_SECRET_MANAGER_CONTRACT_ID,
    credential_profile_id=_CREDENTIAL_PROFILE_ID,
    environment="sandbox",
    selected_provider=SecretProviderKind.PENDING_SELECTION,
    candidate_providers=_CANDIDATE_PROVIDERS,
    required_references=_REQUIRED_REFERENCE_NAMES,
)

SECRET_PROVIDER_BINDING_READINESS_CONTRACTS = MappingProxyType(
    {
        _DECLARED_CONTRACT.readiness_id: _DECLARED_CONTRACT
    }
)

SUPPORTED_SECRET_PROVIDER_BINDING_READINESS = tuple(
    SECRET_PROVIDER_BINDING_READINESS_CONTRACTS
)


def list_secret_provider_binding_readiness_contracts(
) -> tuple[SecretProviderBindingReadinessContract, ...]:
    return tuple(
        SECRET_PROVIDER_BINDING_READINESS_CONTRACTS.values()
    )


def get_secret_provider_binding_readiness_contract(
    readiness_id: str,
) -> SecretProviderBindingReadinessContract:
    normalized = (
        normalize_secret_provider_binding_readiness_id(
            readiness_id
        )
    )

    try:
        return SECRET_PROVIDER_BINDING_READINESS_CONTRACTS[
            normalized
        ]
    except KeyError as exc:
        raise KeyError(
            f"unknown secret-provider readiness: {normalized}"
        ) from exc


def _contract_validation_issues(
    contract: SecretProviderBindingReadinessContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    if not isinstance(
        contract,
        SecretProviderBindingReadinessContract,
    ):
        return ("invalid_provider_readiness_type",)

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
        if intake.runtime_enabled is not False:
            issues.append("intake_runtime_not_disabled")
        if intake.production_allowed is not False:
            issues.append("intake_production_not_disabled")

    if contract.environment != "sandbox":
        issues.append("environment_must_be_sandbox")

    if contract.selected_provider is not (
        SecretProviderKind.PENDING_SELECTION
    ):
        issues.append("provider_selection_must_remain_pending")

    if contract.candidate_providers != _CANDIDATE_PROVIDERS:
        issues.append("candidate_provider_contract_mismatch")

    if contract.required_references != _REQUIRED_REFERENCE_NAMES:
        issues.append("required_reference_contract_mismatch")

    for name in _REQUIRED_TRUE_FLAGS:
        if getattr(contract, name) is not True:
            issues.append(f"{name}_required")

    for name in _UNSAFE_FLAGS:
        if getattr(contract, name) is not False:
            issues.append(f"{name}_must_remain_disabled")

    return tuple(issues)


def validate_secret_provider_binding_readiness_contracts(
    contracts: Iterable[SecretProviderBindingReadinessContract],
) -> tuple[str, ...]:
    issues: list[str] = []
    seen_ids: set[str] = set()

    for index, contract in enumerate(contracts):
        if not isinstance(
            contract,
            SecretProviderBindingReadinessContract,
        ):
            issues.append(
                f"contract_{index}:invalid_provider_readiness_type"
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
        issues.append("no_provider_readiness_declared")

    return tuple(issues)


def validate_secret_provider_binding_readiness_registry(
) -> tuple[str, ...]:
    issues = list(
        validate_secret_provider_binding_readiness_contracts(
            list_secret_provider_binding_readiness_contracts()
        )
    )

    if tuple(
        SECRET_PROVIDER_BINDING_READINESS_CONTRACTS
    ) != SUPPORTED_SECRET_PROVIDER_BINDING_READINESS:
        issues.append("supported_readiness_order_mismatch")

    for key, contract in (
        SECRET_PROVIDER_BINDING_READINESS_CONTRACTS.items()
    ):
        if key != contract.readiness_id:
            issues.append(f"{key}:registry_key_mismatch")

    return tuple(issues)


def assess_secret_provider_binding_readiness(
    readiness_id: str,
    submission: SecretProviderReferenceSubmission | None = None,
) -> SecretProviderBindingReadinessAssessment:
    contract = get_secret_provider_binding_readiness_contract(
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
        provider_selected = False
        selected_provider_reference = (
            SecretProviderKind.PENDING_SELECTION.value
        )
        reference_count = 0
        references_valid = False
        status = (
            SecretProviderBindingReadinessStatus
            .PENDING_PROVIDER_REFERENCE
        )
    elif not isinstance(
        submission,
        SecretProviderReferenceSubmission,
    ):
        raise TypeError(
            "submission must be "
            "SecretProviderReferenceSubmission or None."
        )
    elif submission.readiness_id != contract.readiness_id:
        submission_present = True
        provider_selected = False
        selected_provider_reference = (
            "provider_selection_blocked_reference"
        )
        reference_count = 0
        references_valid = False
        status = SecretProviderBindingReadinessStatus.BLOCKED
    else:
        submission_present = True
        provider_selected = (
            submission.provider_kind in _CANDIDATE_PROVIDERS
        )
        selected_provider_reference = (
            submission.provider_kind.value
        )
        values = tuple(
            getattr(submission, name)
            for name in _REQUIRED_REFERENCE_NAMES
        )
        reference_count = len(values)
        references_valid = all(
            isinstance(value, str) and bool(value)
            for value in values
        )
        status = (
            SecretProviderBindingReadinessStatus
            .REFERENCES_RECEIVED_FOR_REVIEW
            if (
                contract_valid
                and intake_reference_valid
                and provider_selected
                and references_valid
            )
            else SecretProviderBindingReadinessStatus.BLOCKED
        )

    ready = (
        contract_valid
        and intake_reference_valid
        and submission_present
        and provider_selected
        and references_valid
        and reference_count == len(_REQUIRED_REFERENCE_NAMES)
    )

    blockers = list(contract_issues)

    if not submission_present:
        blockers.append("provider_selection_pending")
        blockers.extend(
            f"{name}_pending"
            for name in _REQUIRED_REFERENCE_NAMES
        )

    if submission_present and not provider_selected:
        blockers.append("supported_provider_selection_required")

    if submission_present and not references_valid:
        blockers.append("provider_references_invalid")

    blockers.extend(
        (
            "provider_binding_creation_disabled",
            "provider_client_initialization_disabled",
            "secret_reference_registration_disabled",
            "secret_value_access_disabled",
            "secret_value_storage_disabled",
            "raw_secret_visibility_disabled",
            "authentication_disabled",
            "credential_resolution_disabled",
            "secret_resolution_disabled",
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

    return SecretProviderBindingReadinessAssessment(
        readiness_id=contract.readiness_id,
        intake_id=contract.intake_id,
        status=status,
        contract_valid=contract_valid,
        intake_reference_valid=intake_reference_valid,
        submission_present=submission_present,
        provider_selected=provider_selected,
        selected_provider_reference=(
            selected_provider_reference
        ),
        reference_count=reference_count,
        required_reference_count=len(
            _REQUIRED_REFERENCE_NAMES
        ),
        references_valid=references_valid,
        ready_for_provider_review=ready,
        provider_binding_created=False,
        provider_client_initialized=False,
        secret_reference_registered=False,
        secret_value_accessed=False,
        secret_value_stored=False,
        raw_secret_visible=False,
        authentication_performed=False,
        credentials_resolved=False,
        resolution_allowed=False,
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
