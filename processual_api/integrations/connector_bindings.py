"""Default-deny target and secret reference contracts for connectors.

EXTERNAL-CONNECTIVITY-16B defines Control Plane metadata only. It does not
contain customer endpoints, secret values, external HTTP clients, runtime
dispatch, credential resolution, or production approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
    list_runtime_connector_contracts,
)
from processual_api.integrations.credential_profiles import (
    get_credential_profile,
)
from processual_api.integrations.runtime_contracts import (
    SUPPORTED_CONNECTOR_ENVIRONMENTS,
)

ConnectorBindingEnvironment = Literal["sandbox", "production"]
ConnectorBindingApprovalStatus = Literal["pending_operator_input"]
ConnectorBindingValidationStatus = Literal["unvalidated"]
ConnectorSecretReferenceKind = Literal["customer_vault_reference"]

SUPPORTED_CONNECTOR_BINDING_APPROVAL_STATUSES: tuple[str, ...] = (
    "pending_operator_input",
)
SUPPORTED_CONNECTOR_BINDING_VALIDATION_STATUSES: tuple[str, ...] = (
    "unvalidated",
)
SUPPORTED_CONNECTOR_SECRET_REFERENCE_KINDS: tuple[str, ...] = (
    "customer_vault_reference",
)

_REQUIRED_OPERATOR_INPUTS: tuple[str, ...] = (
    "approved_target_alias",
    "endpoint_reference_metadata",
    "credential_reference_metadata",
    "technical_contact",
    "security_review_record",
)


def _normalize_identifier(value: str) -> str:
    """Normalize an architecture reference identifier."""

    return value.strip().lower().replace("-", "_")


def _validate_identifier(value: str, field_name: str) -> None:
    """Reject empty, non-normalized, or URL-like identifiers."""

    normalized = _normalize_identifier(value)

    if not normalized:
        raise ValueError(f"{field_name} is required.")

    if normalized != value:
        raise ValueError(f"{field_name} must be a normalized lowercase value.")

    if not all(character.isalnum() or character == "_" for character in value):
        raise ValueError(
            f"{field_name} may contain only letters, numbers, and underscores."
        )

    if "://" in value or value.startswith(("http_", "https_")):
        raise ValueError(f"{field_name} cannot contain a literal endpoint.")


def _validate_default_deny(instance: object, fields: tuple[str, ...]) -> None:
    """Require every execution or approval flag to remain false."""

    for field_name in fields:
        if getattr(instance, field_name):
            raise ValueError(
                f"{type(instance).__name__} cannot set {field_name}=True in 16B."
            )


@dataclass(frozen=True, slots=True)
class ConnectorTargetReference:
    """Unresolved target metadata for one connector environment."""

    target_reference_id: str
    connector_id: str
    environment: ConnectorBindingEnvironment
    target_alias: str
    endpoint_reference_name: str
    configured: bool = False
    validated: bool = False
    approved: bool = False
    runtime_enabled: bool = False
    external_http_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.target_reference_id, "target_reference_id")
        _validate_identifier(self.connector_id, "connector_id")
        _validate_identifier(self.target_alias, "target_alias")
        _validate_identifier(
            self.endpoint_reference_name,
            "endpoint_reference_name",
        )

        connector = get_runtime_connector_contract(self.connector_id)

        if self.environment not in SUPPORTED_CONNECTOR_ENVIRONMENTS:
            raise ValueError(
                f"Unsupported connector environment '{self.environment}'."
            )

        if self.environment not in connector.supported_environments:
            raise ValueError(
                f"Connector '{self.connector_id}' does not declare "
                f"environment '{self.environment}'."
            )

        _validate_default_deny(
            self,
            (
                "configured",
                "validated",
                "approved",
                "runtime_enabled",
                "external_http_enabled",
                "production_allowed",
            ),
        )


@dataclass(frozen=True, slots=True)
class ConnectorSecretReference:
    """Unresolved customer-vault reference without secret material."""

    secret_reference_id: str
    credential_profile_id: str
    reference_kind: ConnectorSecretReferenceKind
    provider_reference_name: str
    required: bool = True
    customer_supplied: bool = True
    value_stored: bool = False
    raw_secret_visible: bool = False
    credentials_resolved: bool = False
    runtime_enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.secret_reference_id, "secret_reference_id")
        _validate_identifier(
            self.credential_profile_id,
            "credential_profile_id",
        )
        _validate_identifier(
            self.provider_reference_name,
            "provider_reference_name",
        )

        if self.reference_kind not in SUPPORTED_CONNECTOR_SECRET_REFERENCE_KINDS:
            raise ValueError(
                f"Unsupported secret reference kind '{self.reference_kind}'."
            )

        profile = get_credential_profile(self.credential_profile_id)

        if profile.approved_for_runtime or profile.runtime_connector_approved:
            raise ValueError(
                f"Credential profile '{self.credential_profile_id}' must remain "
                "non-runtime."
            )

        if not self.required:
            raise ValueError("16B secret references must remain required.")

        if not self.customer_supplied:
            raise ValueError("16B secret references must remain customer supplied.")

        _validate_default_deny(
            self,
            (
                "value_stored",
                "raw_secret_visible",
                "credentials_resolved",
                "runtime_enabled",
                "production_allowed",
            ),
        )


@dataclass(frozen=True, slots=True)
class ConnectorEnvironmentBinding:
    """Unapproved link between connector, target, and secret references."""

    binding_id: str
    connector_id: str
    environment: ConnectorBindingEnvironment
    target_reference_id: str
    secret_reference_ids: tuple[str, ...]
    required_operator_inputs: tuple[str, ...]
    approval_status: ConnectorBindingApprovalStatus = "pending_operator_input"
    validation_status: ConnectorBindingValidationStatus = "unvalidated"
    configured: bool = False
    validated: bool = False
    approved: bool = False
    runtime_enabled: bool = False
    external_http_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False
    credentials_resolved: bool = False

    def __post_init__(self) -> None:
        _validate_identifier(self.binding_id, "binding_id")
        _validate_identifier(self.connector_id, "connector_id")
        _validate_identifier(self.target_reference_id, "target_reference_id")
        connector = get_runtime_connector_contract(self.connector_id)

        if self.environment not in SUPPORTED_CONNECTOR_ENVIRONMENTS:
            raise ValueError(
                f"Unsupported connector environment '{self.environment}'."
            )

        if self.environment not in connector.supported_environments:
            raise ValueError(
                f"Connector '{self.connector_id}' does not declare "
                f"environment '{self.environment}'."
            )

        if not self.secret_reference_ids:
            raise ValueError(
                f"Binding '{self.binding_id}' must declare secret references."
            )

        if len(set(self.secret_reference_ids)) != len(self.secret_reference_ids):
            raise ValueError(
                f"Binding '{self.binding_id}' has duplicate secret references."
            )

        for reference_id in self.secret_reference_ids:
            _validate_identifier(reference_id, "secret_reference_id")

        if not self.required_operator_inputs:
            raise ValueError(
                f"Binding '{self.binding_id}' must declare operator inputs."
            )

        if len(set(self.required_operator_inputs)) != len(
            self.required_operator_inputs
        ):
            raise ValueError(
                f"Binding '{self.binding_id}' has duplicate operator inputs."
            )

        for input_name in self.required_operator_inputs:
            _validate_identifier(input_name, "required_operator_input")

        if self.approval_status not in (
            SUPPORTED_CONNECTOR_BINDING_APPROVAL_STATUSES
        ):
            raise ValueError(
                f"Unsupported binding approval status '{self.approval_status}'."
            )

        if self.validation_status not in (
            SUPPORTED_CONNECTOR_BINDING_VALIDATION_STATUSES
        ):
            raise ValueError(
                f"Unsupported binding validation status "
                f"'{self.validation_status}'."
            )

        _validate_default_deny(
            self,
            (
                "configured",
                "validated",
                "approved",
                "runtime_enabled",
                "external_http_enabled",
                "production_allowed",
                "automatic_activation_allowed",
                "credentials_resolved",
            ),
        )


_runtime_connectors = list_runtime_connector_contracts()
_profile_ids = tuple(
    sorted(
        {
            profile_id
            for connector in _runtime_connectors
            for profile_id in connector.authentication_profile_ids
        }
    )
)

_SECRET_REFERENCES: dict[str, ConnectorSecretReference] = {
    f"{profile_id}_secret_reference": ConnectorSecretReference(
        secret_reference_id=f"{profile_id}_secret_reference",
        credential_profile_id=profile_id,
        reference_kind="customer_vault_reference",
        provider_reference_name=f"{profile_id}_pending_vault_reference",
    )
    for profile_id in _profile_ids
}

_TARGET_REFERENCES: dict[str, ConnectorTargetReference] = {}
_ENVIRONMENT_BINDINGS: dict[str, ConnectorEnvironmentBinding] = {}

for _connector in _runtime_connectors:
    for _environment in _connector.supported_environments:
        _target_reference_id = (
            f"{_connector.connector_id}_{_environment}_target_reference"
        )
        _binding_id = f"{_connector.connector_id}_{_environment}_binding"
        _secret_reference_ids = tuple(
            f"{profile_id}_secret_reference"
            for profile_id in _connector.authentication_profile_ids
        )

        _TARGET_REFERENCES[_target_reference_id] = ConnectorTargetReference(
            target_reference_id=_target_reference_id,
            connector_id=_connector.connector_id,
            environment=_environment,
            target_alias=(
                f"{_connector.connector_id}_{_environment}_pending_target"
            ),
            endpoint_reference_name=(
                f"{_connector.connector_id}_{_environment}_endpoint_reference"
            ),
        )

        _ENVIRONMENT_BINDINGS[_binding_id] = ConnectorEnvironmentBinding(
            binding_id=_binding_id,
            connector_id=_connector.connector_id,
            environment=_environment,
            target_reference_id=_target_reference_id,
            secret_reference_ids=_secret_reference_ids,
            required_operator_inputs=_REQUIRED_OPERATOR_INPUTS,
        )


CONNECTOR_SECRET_REFERENCES = MappingProxyType(_SECRET_REFERENCES)
CONNECTOR_TARGET_REFERENCES = MappingProxyType(_TARGET_REFERENCES)
CONNECTOR_ENVIRONMENT_BINDINGS = MappingProxyType(_ENVIRONMENT_BINDINGS)

SUPPORTED_CONNECTOR_SECRET_REFERENCES: tuple[str, ...] = tuple(
    CONNECTOR_SECRET_REFERENCES
)
SUPPORTED_CONNECTOR_TARGET_REFERENCES: tuple[str, ...] = tuple(
    CONNECTOR_TARGET_REFERENCES
)
SUPPORTED_CONNECTOR_ENVIRONMENT_BINDINGS: tuple[str, ...] = tuple(
    CONNECTOR_ENVIRONMENT_BINDINGS
)


def list_connector_secret_references() -> tuple[ConnectorSecretReference, ...]:
    """Return secret references in stable registry order."""

    return tuple(CONNECTOR_SECRET_REFERENCES.values())


def list_connector_target_references() -> tuple[ConnectorTargetReference, ...]:
    """Return target references in stable registry order."""

    return tuple(CONNECTOR_TARGET_REFERENCES.values())


def list_connector_environment_bindings() -> tuple[
    ConnectorEnvironmentBinding,
    ...,
]:
    """Return environment bindings in stable registry order."""

    return tuple(CONNECTOR_ENVIRONMENT_BINDINGS.values())


def get_connector_secret_reference(
    secret_reference_id: str,
) -> ConnectorSecretReference:
    """Return one secret reference by normalized identifier."""

    normalized_id = _normalize_identifier(secret_reference_id)

    try:
        return CONNECTOR_SECRET_REFERENCES[normalized_id]
    except KeyError as exc:
        raise KeyError(
            f"Unsupported connector secret reference '{secret_reference_id}'."
        ) from exc


def get_connector_target_reference(
    target_reference_id: str,
) -> ConnectorTargetReference:
    """Return one target reference by normalized identifier."""

    normalized_id = _normalize_identifier(target_reference_id)

    try:
        return CONNECTOR_TARGET_REFERENCES[normalized_id]
    except KeyError as exc:
        raise KeyError(
            f"Unsupported connector target reference '{target_reference_id}'."
        ) from exc


def get_connector_environment_binding(
    binding_id: str,
) -> ConnectorEnvironmentBinding:
    """Return one environment binding by normalized identifier."""

    normalized_id = _normalize_identifier(binding_id)

    try:
        return CONNECTOR_ENVIRONMENT_BINDINGS[normalized_id]
    except KeyError as exc:
        raise KeyError(
            f"Unsupported connector environment binding '{binding_id}'."
        ) from exc


def validate_connector_binding_contracts(
    target_references: tuple[ConnectorTargetReference, ...],
    secret_references: tuple[ConnectorSecretReference, ...],
    environment_bindings: tuple[ConnectorEnvironmentBinding, ...],
) -> tuple[str, ...]:
    """Return deterministic issues for one set of 16B contracts."""

    issues: list[str] = []

    target_ids = tuple(
        reference.target_reference_id for reference in target_references
    )
    secret_ids = tuple(
        reference.secret_reference_id for reference in secret_references
    )
    binding_ids = tuple(binding.binding_id for binding in environment_bindings)

    if len(set(target_ids)) != len(target_ids):
        issues.append("Connector target reference ids must be unique.")

    if len(set(secret_ids)) != len(secret_ids):
        issues.append("Connector secret reference ids must be unique.")

    if len(set(binding_ids)) != len(binding_ids):
        issues.append("Connector environment binding ids must be unique.")

    target_by_id = {
        reference.target_reference_id: reference
        for reference in target_references
    }
    secret_by_id = {
        reference.secret_reference_id: reference
        for reference in secret_references
    }

    expected_pairs = {
        (connector.connector_id, environment)
        for connector in list_runtime_connector_contracts()
        for environment in connector.supported_environments
    }
    actual_target_pairs = {
        (reference.connector_id, reference.environment)
        for reference in target_references
    }
    actual_binding_pairs = {
        (binding.connector_id, binding.environment)
        for binding in environment_bindings
    }

    if actual_target_pairs != expected_pairs:
        issues.append(
            "Connector target references do not cover every declared environment."
        )

    if actual_binding_pairs != expected_pairs:
        issues.append(
            "Connector environment bindings do not cover every declared environment."
        )

    expected_profile_ids = {
        profile_id
        for connector in list_runtime_connector_contracts()
        for profile_id in connector.authentication_profile_ids
    }
    actual_profile_ids = {
        reference.credential_profile_id for reference in secret_references
    }

    if actual_profile_ids != expected_profile_ids:
        issues.append(
            "Connector secret references do not cover every authentication profile."
        )

    for binding in environment_bindings:
        target = target_by_id.get(binding.target_reference_id)

        if target is None:
            issues.append(
                f"Binding '{binding.binding_id}' references an unknown target."
            )
        elif (
            target.connector_id != binding.connector_id
            or target.environment != binding.environment
        ):
            issues.append(
                f"Binding '{binding.binding_id}' target does not match its "
                "connector environment."
            )

        connector = get_runtime_connector_contract(binding.connector_id)
        expected_binding_profiles = set(connector.authentication_profile_ids)
        actual_binding_profiles: set[str] = set()

        for reference_id in binding.secret_reference_ids:
            reference = secret_by_id.get(reference_id)

            if reference is None:
                issues.append(
                    f"Binding '{binding.binding_id}' references unknown secret "
                    f"'{reference_id}'."
                )
                continue

            actual_binding_profiles.add(reference.credential_profile_id)

        if actual_binding_profiles != expected_binding_profiles:
            issues.append(
                f"Binding '{binding.binding_id}' secret references do not match "
                "its connector authentication profiles."
            )

    return tuple(issues)


def validate_connector_binding_registry() -> tuple[str, ...]:
    """Return deterministic integrity issues for the immutable registry."""

    return validate_connector_binding_contracts(
        list_connector_target_references(),
        list_connector_secret_references(),
        list_connector_environment_bindings(),
    )


__all__ = [
    "CONNECTOR_ENVIRONMENT_BINDINGS",
    "CONNECTOR_SECRET_REFERENCES",
    "CONNECTOR_TARGET_REFERENCES",
    "SUPPORTED_CONNECTOR_BINDING_APPROVAL_STATUSES",
    "SUPPORTED_CONNECTOR_BINDING_VALIDATION_STATUSES",
    "SUPPORTED_CONNECTOR_ENVIRONMENT_BINDINGS",
    "SUPPORTED_CONNECTOR_SECRET_REFERENCE_KINDS",
    "SUPPORTED_CONNECTOR_SECRET_REFERENCES",
    "SUPPORTED_CONNECTOR_TARGET_REFERENCES",
    "ConnectorBindingApprovalStatus",
    "ConnectorBindingEnvironment",
    "ConnectorBindingValidationStatus",
    "ConnectorEnvironmentBinding",
    "ConnectorSecretReference",
    "ConnectorSecretReferenceKind",
    "ConnectorTargetReference",
    "get_connector_environment_binding",
    "get_connector_secret_reference",
    "get_connector_target_reference",
    "list_connector_environment_bindings",
    "list_connector_secret_references",
    "list_connector_target_references",
    "validate_connector_binding_contracts",
    "validate_connector_binding_registry",
]
