"""Reference-only secret manager contracts for governed sandbox pilots.

This module validates a customer-managed vault reference graph. It never
reads, stores, decrypts, resolves, transmits, logs, or exposes credential
material.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from processual_api.integrations.connector_bindings import (
    ConnectorSecretReference,
    get_connector_secret_reference,
)
from processual_api.integrations.credential_profiles import (
    CredentialProfile,
    get_credential_profile,
)
from processual_api.integrations.sandbox_pilot import (
    ConnectorSandboxPilotContract,
    get_connector_sandbox_pilot_contract,
)

__all__ = [
    "CONNECTOR_SECRET_MANAGER_CONTRACTS",
    "SUPPORTED_CONNECTOR_SECRET_MANAGER_CONTRACTS",
    "ConnectorSecretManagerAssessment",
    "ConnectorSecretManagerContract",
    "ConnectorSecretManagerMode",
    "ConnectorSecretManagerStatus",
    "assess_connector_secret_manager_contract",
    "get_connector_secret_manager_contract",
    "list_connector_secret_manager_contracts",
    "normalize_connector_secret_manager_contract_id",
    "validate_connector_secret_manager_contracts",
    "validate_connector_secret_manager_registry",
]


class ConnectorSecretManagerMode(StrEnum):
    """Supported reference-only secret ownership modes."""

    CUSTOMER_MANAGED_VAULT_REFERENCE = (
        "customer_managed_vault_reference"
    )


class ConnectorSecretManagerStatus(StrEnum):
    """Non-resolving states supported by the R2 contract."""

    PENDING_CUSTOMER_VAULT_REFERENCE = (
        "pending_customer_vault_reference"
    )
    BLOCKED = "blocked"


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

_EXPECTED_SUPPORTED_AUTH_METHODS: Final[tuple[str, ...]] = (
    "api_key_reference",
    "oauth_client_reference",
    "mtls_certificate_reference",
    "customer_vault_reference",
)

_EXPECTED_FORBIDDEN_SECRET_MATERIAL: Final[tuple[str, ...]] = (
    "raw API key values",
    "raw OAuth client secrets",
    "raw passwords",
    "raw access tokens",
    "raw refresh tokens",
    "private key material",
    "certificate private keys",
    "webhook signing secret values",
    "database connection strings",
)

_EXPECTED_REQUIRED_CUSTOMER_INPUTS: Final[tuple[str, ...]] = (
    "api_documentation",
    "sandbox_access",
    "test_credentials_policy",
    "scope_matrix",
    "technical_contact",
    "acceptance_criteria",
    "security_requirements",
    "credential_owner",
    "rotation_policy",
    "customer_endpoint_inventory",
)

_EXPECTED_REQUIRED_SECURITY_CONTROLS: Final[tuple[str, ...]] = (
    "enterprise_review",
    "security_review",
    "sandbox_before_production",
    "least_privilege_scopes",
    "supervisor_approval_for_production_credentials",
    "no_raw_secrets_in_support_notes",
    "customer_vault_or_reference_storage",
    "audit_logging_required",
)

_SELECTED_CONTRACT_ID: Final[str] = (
    "telecom_operations_customer_vault_secret_manager_contract"
)

_SELECTED_PILOT_ID: Final[str] = (
    "telecom_ticketing_read_only_sandbox_pilot"
)

_SELECTED_SECRET_REFERENCE_ID: Final[str] = (
    "telecom_operations_api_reference_secret_reference"
)

_SELECTED_CREDENTIAL_PROFILE_ID: Final[str] = (
    "telecom_operations_api_reference"
)

_SELECTED_PROVIDER_REFERENCE_NAME: Final[str] = (
    "telecom_operations_api_reference_pending_vault_reference"
)

_SELECTED_REFERENCE_KIND: Final[str] = (
    "customer_vault_reference"
)

_UNSAFE_CONTRACT_FLAGS: Final[tuple[str, ...]] = (
    "reference_registered",
    "reference_validated",
    "customer_authorization_present",
    "operator_approval_present",
    "security_review_completed",
    "rotation_policy_confirmed",
    "resolution_allowed",
    "credentials_resolved",
    "value_stored",
    "raw_secret_visible",
    "runtime_enabled",
    "production_allowed",
)

_UNSAFE_ASSESSMENT_FLAGS: Final[tuple[str, ...]] = (
    "reference_registered",
    "reference_validated",
    "customer_authorization_present",
    "operator_approval_present",
    "security_review_completed",
    "rotation_policy_confirmed",
    "resolution_allowed",
    "credentials_resolved",
    "value_stored",
    "raw_secret_visible",
    "runtime_enabled",
    "production_allowed",
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
class ConnectorSecretManagerContract:
    """Immutable customer-vault reference contract."""

    contract_id: str
    pilot_id: str
    secret_reference_id: str
    credential_profile_id: str
    provider_reference_name: str
    reference_kind: str
    mode: ConnectorSecretManagerMode
    supported_auth_methods: tuple[str, ...]
    forbidden_secret_material: tuple[str, ...]
    required_customer_inputs: tuple[str, ...]
    required_security_controls: tuple[str, ...]
    customer_supplied: bool
    customer_authorization_required: bool
    operator_approval_required: bool
    security_review_required: bool
    rotation_policy_required: bool
    sandbox_only: bool
    status: ConnectorSecretManagerStatus = (
        ConnectorSecretManagerStatus
        .PENDING_CUSTOMER_VAULT_REFERENCE
    )
    reference_registered: bool = False
    reference_validated: bool = False
    customer_authorization_present: bool = False
    operator_approval_present: bool = False
    security_review_completed: bool = False
    rotation_policy_confirmed: bool = False
    resolution_allowed: bool = False
    credentials_resolved: bool = False
    value_stored: bool = False
    raw_secret_visible: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "contract_id",
            "pilot_id",
            "secret_reference_id",
            "credential_profile_id",
            "provider_reference_name",
            "reference_kind",
        ):
            _validate_reference_text(
                field_name,
                getattr(self, field_name),
            )

        for field_name in (
            "supported_auth_methods",
            "forbidden_secret_material",
            "required_customer_inputs",
            "required_security_controls",
        ):
            _validate_reference_sequence(
                field_name,
                getattr(self, field_name),
            )

        if not isinstance(
            self.mode,
            ConnectorSecretManagerMode,
        ):
            try:
                normalized_mode = ConnectorSecretManagerMode(
                    self.mode
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported secret manager mode."
                ) from exc

            object.__setattr__(
                self,
                "mode",
                normalized_mode,
            )

        if not isinstance(
            self.status,
            ConnectorSecretManagerStatus,
        ):
            try:
                normalized_status = ConnectorSecretManagerStatus(
                    self.status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported secret manager status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        if self.mode is not (
            ConnectorSecretManagerMode
            .CUSTOMER_MANAGED_VAULT_REFERENCE
        ):
            raise ValueError(
                "R2 must remain customer-managed-vault based."
            )

        if self.reference_kind != "customer_vault_reference":
            raise ValueError(
                "R2 reference kind must remain customer_vault_reference."
            )

        if not self.provider_reference_name.endswith(
            "_pending_vault_reference"
        ):
            raise ValueError(
                "Provider reference must remain a pending reference."
            )

        for field_name in (
            "customer_supplied",
            "customer_authorization_required",
            "operator_approval_required",
            "security_review_required",
            "rotation_policy_required",
            "sandbox_only",
        ):
            if getattr(self, field_name) is not True:
                raise ValueError(
                    f"{field_name} must remain True in 16E-R2."
                )

        if self.status is not (
            ConnectorSecretManagerStatus
            .PENDING_CUSTOMER_VAULT_REFERENCE
        ):
            raise ValueError(
                "R2 status must remain pending customer vault reference."
            )

        for field_name in _UNSAFE_CONTRACT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R2."
                )


@dataclass(frozen=True, slots=True)
class ConnectorSecretManagerAssessment:
    """Immutable non-resolving projection of secret readiness."""

    contract_id: str
    status: ConnectorSecretManagerStatus
    contract_valid: bool
    reference_graph_valid: bool
    provider_reference_pending: bool
    customer_authorization_present: bool
    operator_approval_present: bool
    security_review_completed: bool
    rotation_policy_confirmed: bool
    reference_registered: bool
    reference_validated: bool
    resolution_allowed: bool
    credentials_resolved: bool
    value_stored: bool
    raw_secret_visible: bool
    runtime_enabled: bool
    production_allowed: bool
    blocker_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_reference_text(
            "contract_id",
            self.contract_id,
        )

        if not isinstance(
            self.status,
            ConnectorSecretManagerStatus,
        ):
            try:
                normalized_status = ConnectorSecretManagerStatus(
                    self.status
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "Unsupported secret manager assessment status."
                ) from exc

            object.__setattr__(
                self,
                "status",
                normalized_status,
            )

        boolean_fields = (
            "contract_valid",
            "reference_graph_valid",
            "provider_reference_pending",
            *_UNSAFE_ASSESSMENT_FLAGS,
        )

        for field_name in boolean_fields:
            if type(getattr(self, field_name)) is not bool:
                raise TypeError(
                    f"{field_name} must be a boolean."
                )

        if self.provider_reference_pending is not True:
            raise ValueError(
                "R2 provider reference must remain pending."
            )

        for field_name in _UNSAFE_ASSESSMENT_FLAGS:
            if getattr(self, field_name) is not False:
                raise ValueError(
                    f"{field_name} must remain False in 16E-R2."
                )

        _validate_reference_sequence(
            "blocker_codes",
            self.blocker_codes,
        )


def normalize_connector_secret_manager_contract_id(
    contract_id: str,
) -> str:
    """Normalize a secret manager contract identifier."""

    if not isinstance(contract_id, str):
        raise TypeError(
            "contract_id must be a string."
        )

    normalized = contract_id.strip().casefold()

    _validate_reference_text(
        "contract_id",
        normalized,
    )

    return normalized


def _secret_reference_is_default_deny(
    secret_reference: ConnectorSecretReference,
) -> bool:
    if _enum_value(
        secret_reference.reference_kind
    ) != "customer_vault_reference":
        return False

    if secret_reference.required is not True:
        return False

    if secret_reference.customer_supplied is not True:
        return False

    for field_name in (
        "value_stored",
        "raw_secret_visible",
        "credentials_resolved",
        "runtime_enabled",
        "production_allowed",
    ):
        if getattr(secret_reference, field_name) is not False:
            return False

    return True


def _credential_profile_is_default_deny(
    profile: CredentialProfile,
) -> bool:
    supported_auth_methods = tuple(
        _enum_value(value)
        for value in profile.supported_auth_methods
    )

    if supported_auth_methods != _EXPECTED_SUPPORTED_AUTH_METHODS:
        return False

    if profile.forbidden_secret_material != (
        _EXPECTED_FORBIDDEN_SECRET_MATERIAL
    ):
        return False

    if profile.required_customer_inputs != (
        _EXPECTED_REQUIRED_CUSTOMER_INPUTS
    ):
        return False

    if profile.required_security_controls != (
        _EXPECTED_REQUIRED_SECURITY_CONTROLS
    ):
        return False

    for field_name in (
        "rotation_policy_required",
        "sandbox_required",
        "production_credential_approval_required",
        "technical_contact_required",
        "security_review_required",
        "customer_endpoint_inventory_required",
    ):
        if getattr(profile, field_name) is not True:
            return False

    if profile.approved_for_runtime is not False:
        return False

    return True


def _pilot_is_default_deny(
    pilot: ConnectorSandboxPilotContract,
) -> bool:
    if pilot.environment != "sandbox":
        return False

    if pilot.access_mode != "read":
        return False

    if pilot.sandbox_only is not True:
        return False

    if pilot.read_only is not True:
        return False

    if pilot.operator_approval_required is not True:
        return False

    if pilot.customer_approval_required is not True:
        return False

    for field_name in (
        "configured",
        "validated",
        "approved",
        "action_execution_allowed",
        "runtime_enabled",
        "external_http_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "credentials_resolved",
    ):
        if getattr(pilot, field_name) is not False:
            return False

    return True


def _contract_validation_issues(
    contract: ConnectorSecretManagerContract,
) -> tuple[str, ...]:
    issues: list[str] = []

    try:
        secret_reference = get_connector_secret_reference(
            contract.secret_reference_id
        )
    except KeyError:
        secret_reference = None
        issues.append(
            f"{contract.contract_id}:secret_reference_not_found"
        )

    try:
        profile = get_credential_profile(
            contract.credential_profile_id
        )
    except KeyError:
        profile = None
        issues.append(
            f"{contract.contract_id}:credential_profile_not_found"
        )

    try:
        pilot = get_connector_sandbox_pilot_contract(
            contract.pilot_id
        )
    except KeyError:
        pilot = None
        issues.append(
            f"{contract.contract_id}:sandbox_pilot_not_found"
        )

    if secret_reference is not None:
        if secret_reference.credential_profile_id != (
            contract.credential_profile_id
        ):
            issues.append(
                f"{contract.contract_id}:"
                "secret_profile_mismatch"
            )

        if secret_reference.provider_reference_name != (
            contract.provider_reference_name
        ):
            issues.append(
                f"{contract.contract_id}:"
                "provider_reference_mismatch"
            )

        if _enum_value(secret_reference.reference_kind) != (
            contract.reference_kind
        ):
            issues.append(
                f"{contract.contract_id}:"
                "reference_kind_mismatch"
            )

        if secret_reference.customer_supplied != (
            contract.customer_supplied
        ):
            issues.append(
                f"{contract.contract_id}:"
                "customer_supplied_mismatch"
            )

        if not _secret_reference_is_default_deny(
            secret_reference
        ):
            issues.append(
                f"{contract.contract_id}:"
                "secret_reference_not_default_deny"
            )

    if profile is not None:
        supported_auth_methods = tuple(
            _enum_value(value)
            for value in profile.supported_auth_methods
        )

        if supported_auth_methods != (
            contract.supported_auth_methods
        ):
            issues.append(
                f"{contract.contract_id}:"
                "supported_auth_methods_mismatch"
            )

        if profile.forbidden_secret_material != (
            contract.forbidden_secret_material
        ):
            issues.append(
                f"{contract.contract_id}:"
                "forbidden_material_mismatch"
            )

        if profile.required_customer_inputs != (
            contract.required_customer_inputs
        ):
            issues.append(
                f"{contract.contract_id}:"
                "required_customer_inputs_mismatch"
            )

        if profile.required_security_controls != (
            contract.required_security_controls
        ):
            issues.append(
                f"{contract.contract_id}:"
                "required_security_controls_mismatch"
            )

        if profile.rotation_policy_required != (
            contract.rotation_policy_required
        ):
            issues.append(
                f"{contract.contract_id}:"
                "rotation_policy_mismatch"
            )

        if profile.security_review_required != (
            contract.security_review_required
        ):
            issues.append(
                f"{contract.contract_id}:"
                "security_review_mismatch"
            )

        if not _credential_profile_is_default_deny(
            profile
        ):
            issues.append(
                f"{contract.contract_id}:"
                "credential_profile_not_default_deny"
            )

    if pilot is not None:
        if contract.secret_reference_id not in (
            pilot.secret_reference_ids
        ):
            issues.append(
                f"{contract.contract_id}:"
                "pilot_secret_reference_mismatch"
            )

        if contract.credential_profile_id not in (
            pilot.credential_profile_ids
        ):
            issues.append(
                f"{contract.contract_id}:"
                "pilot_credential_profile_mismatch"
            )

        if not _pilot_is_default_deny(pilot):
            issues.append(
                f"{contract.contract_id}:"
                "sandbox_pilot_not_default_deny"
            )

    return tuple(issues)


def validate_connector_secret_manager_contracts(
    contracts: tuple[ConnectorSecretManagerContract, ...],
) -> tuple[str, ...]:
    """Validate secret-manager contracts against governed references."""

    issues: list[str] = []
    seen_ids: set[str] = set()

    for contract in contracts:
        if not isinstance(
            contract,
            ConnectorSecretManagerContract,
        ):
            issues.append(
                "secret_manager_contract_type_invalid"
            )
            continue

        if contract.contract_id in seen_ids:
            issues.append(
                f"{contract.contract_id}:duplicate_contract_id"
            )

        seen_ids.add(contract.contract_id)

        issues.extend(
            _contract_validation_issues(contract)
        )

    return tuple(issues)


_TELECOM_OPERATIONS_CUSTOMER_VAULT_CONTRACT = (
    ConnectorSecretManagerContract(
        contract_id=_SELECTED_CONTRACT_ID,
        pilot_id=_SELECTED_PILOT_ID,
        secret_reference_id=_SELECTED_SECRET_REFERENCE_ID,
        credential_profile_id=_SELECTED_CREDENTIAL_PROFILE_ID,
        provider_reference_name=_SELECTED_PROVIDER_REFERENCE_NAME,
        reference_kind=_SELECTED_REFERENCE_KIND,
        mode=(
            ConnectorSecretManagerMode
            .CUSTOMER_MANAGED_VAULT_REFERENCE
        ),
        supported_auth_methods=(
            _EXPECTED_SUPPORTED_AUTH_METHODS
        ),
        forbidden_secret_material=(
            _EXPECTED_FORBIDDEN_SECRET_MATERIAL
        ),
        required_customer_inputs=(
            _EXPECTED_REQUIRED_CUSTOMER_INPUTS
        ),
        required_security_controls=(
            _EXPECTED_REQUIRED_SECURITY_CONTROLS
        ),
        customer_supplied=True,
        customer_authorization_required=True,
        operator_approval_required=True,
        security_review_required=True,
        rotation_policy_required=True,
        sandbox_only=True,
    )
)

_CONNECTOR_SECRET_MANAGER_CONTRACTS = {
    _TELECOM_OPERATIONS_CUSTOMER_VAULT_CONTRACT.contract_id: (
        _TELECOM_OPERATIONS_CUSTOMER_VAULT_CONTRACT
    ),
}

CONNECTOR_SECRET_MANAGER_CONTRACTS = MappingProxyType(
    _CONNECTOR_SECRET_MANAGER_CONTRACTS
)

SUPPORTED_CONNECTOR_SECRET_MANAGER_CONTRACTS = tuple(
    CONNECTOR_SECRET_MANAGER_CONTRACTS
)


def list_connector_secret_manager_contracts(
) -> tuple[ConnectorSecretManagerContract, ...]:
    """List immutable secret manager declarations."""

    return tuple(
        CONNECTOR_SECRET_MANAGER_CONTRACTS.values()
    )


def get_connector_secret_manager_contract(
    contract_id: str,
) -> ConnectorSecretManagerContract:
    """Return one normalized secret manager contract."""

    normalized_id = (
        normalize_connector_secret_manager_contract_id(
            contract_id
        )
    )

    try:
        return CONNECTOR_SECRET_MANAGER_CONTRACTS[
            normalized_id
        ]
    except KeyError as exc:
        raise KeyError(
            f"Unknown connector secret manager contract: "
            f"{normalized_id}"
        ) from exc


def validate_connector_secret_manager_registry(
) -> tuple[str, ...]:
    """Validate the built-in secret manager contract registry."""

    return validate_connector_secret_manager_contracts(
        list_connector_secret_manager_contracts()
    )


def assess_connector_secret_manager_contract(
    contract_id: str,
) -> ConnectorSecretManagerAssessment:
    """Project current blockers without resolving credential material."""

    contract = get_connector_secret_manager_contract(
        contract_id
    )

    contract_issues = _contract_validation_issues(
        contract
    )

    blockers: list[str] = []

    if contract_issues:
        blockers.append(
            "secret_manager_contract_invalid"
        )

    blockers.extend(
        (
            "customer_vault_reference_pending",
            "reference_registration_pending",
            "reference_validation_pending",
            "customer_authorization_pending",
            "operator_approval_pending",
            "security_review_pending",
            "rotation_policy_pending",
            "secret_resolution_disabled",
            "runtime_disabled",
            "production_disabled",
        )
    )

    unique_blockers = tuple(
        dict.fromkeys(blockers)
    )

    status = (
        ConnectorSecretManagerStatus.BLOCKED
        if contract_issues
        else (
            ConnectorSecretManagerStatus
            .PENDING_CUSTOMER_VAULT_REFERENCE
        )
    )

    return ConnectorSecretManagerAssessment(
        contract_id=contract.contract_id,
        status=status,
        contract_valid=not contract_issues,
        reference_graph_valid=not contract_issues,
        provider_reference_pending=True,
        customer_authorization_present=False,
        operator_approval_present=False,
        security_review_completed=False,
        rotation_policy_confirmed=False,
        reference_registered=False,
        reference_validated=False,
        resolution_allowed=False,
        credentials_resolved=False,
        value_stored=False,
        raw_secret_visible=False,
        runtime_enabled=False,
        production_allowed=False,
        blocker_codes=unique_blockers,
    )
