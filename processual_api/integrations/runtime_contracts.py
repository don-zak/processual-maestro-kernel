"""Default-deny architecture contracts for future external connectors.

TELECOM-CONNECTIVITY-16A defines Control Plane objects only. It does not add
network transports, endpoints, credentials, dispatch, workers, queues, or
executable customer connectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.credential_profiles import (
    get_credential_profile,
)
from processual_api.integrations.scope_catalog import get_integration_scope

ConnectorContractFamily = Literal[
    "tm_forum",
    "camara",
    "proprietary",
    "legacy",
    "generic_enterprise",
]

ConnectorCapabilityAccess = Literal[
    "read",
    "write",
    "restricted",
]

SUPPORTED_CONNECTOR_CONTRACT_FAMILIES: tuple[str, ...] = (
    "tm_forum",
    "camara",
    "proprietary",
    "legacy",
    "generic_enterprise",
)

SUPPORTED_CONNECTOR_ENVIRONMENTS: tuple[str, ...] = (
    "sandbox",
    "production",
)

SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS: tuple[str, ...] = (
    "public",
    "internal",
    "customer_confidential",
    "subscriber_personal",
    "billing_sensitive",
    "network_operational",
)


def normalize_runtime_connector_id(connector_id: str) -> str:
    """Normalize a connector identifier for registry lookup."""

    return connector_id.strip().lower().replace("-", "_")


@dataclass(frozen=True, slots=True)
class ConnectorCapability:
    """Scope-backed capability that remains disabled in 16A."""

    capability_id: str
    scope_id: str
    access_mode: ConnectorCapabilityAccess
    approval_required: bool
    sandbox_only: bool
    enabled: bool = False
    production_allowed: bool = False

    def __post_init__(self) -> None:
        if not self.capability_id:
            raise ValueError("Connector capability id is required.")

        if self.capability_id != self.capability_id.strip().lower():
            raise ValueError(
                "Connector capability ids must be normalized lowercase values."
            )

        if "." not in self.capability_id:
            raise ValueError(
                "Connector capability ids must use dot-separated names."
            )

        scope = get_integration_scope(self.scope_id)

        if scope.access_level != self.access_mode:
            raise ValueError(
                f"Capability '{self.capability_id}' access mode does not "
                f"match scope '{scope.scope_id}'."
            )

        if (
            self.approval_required
            is not scope.requires_supervisor_approval
        ):
            raise ValueError(
                f"Capability '{self.capability_id}' must preserve the "
                f"approval posture of scope '{scope.scope_id}'."
            )

        if self.access_mode != "read" and not self.sandbox_only:
            raise ValueError(
                f"Capability '{self.capability_id}' must remain "
                f"sandbox-only."
            )

        if self.enabled:
            raise ValueError(
                f"Capability '{self.capability_id}' cannot be enabled in 16A."
            )

        if self.production_allowed:
            raise ValueError(
                f"Capability '{self.capability_id}' cannot allow production."
            )


@dataclass(frozen=True, slots=True)
class ConnectorRuntimeContract:
    """Disabled boundary for a future isolated connector runtime."""

    connector_id: str
    display_name: str
    connector_version: str
    adapter_contract_id: str
    contract_family: ConnectorContractFamily
    supported_environments: tuple[str, ...]
    capabilities: tuple[ConnectorCapability, ...]
    authentication_profile_ids: tuple[str, ...]
    data_classifications: tuple[str, ...]
    mapping_version: str
    external_api_version: str
    requires_enterprise_review: bool = True
    requires_sandbox_before_production: bool = True
    read_allowed: bool = False
    write_allowed: bool = False
    runtime_enabled: bool = False
    external_http_enabled: bool = False
    production_allowed: bool = False
    automatic_activation_allowed: bool = False
    credentials_storage_allowed: bool = False
    raw_secret_visible: bool = False

    def __post_init__(self) -> None:
        normalized_id = normalize_runtime_connector_id(self.connector_id)

        if not normalized_id:
            raise ValueError("Runtime connector id is required.")

        if normalized_id != self.connector_id:
            raise ValueError(
                "Runtime connector ids must be normalized lowercase values."
            )

        if not all(
            character.isalnum() or character == "_"
            for character in self.connector_id
        ):
            raise ValueError(
                "Runtime connector ids may contain only letters, numbers, "
                "and underscores."
            )

        required_text_fields = {
            "display_name": self.display_name,
            "connector_version": self.connector_version,
            "mapping_version": self.mapping_version,
            "external_api_version": self.external_api_version,
        }

        for field_name, value in required_text_fields.items():
            if not value.strip():
                raise ValueError(
                    f"Runtime connector field '{field_name}' is required."
                )

        if self.contract_family not in (
            SUPPORTED_CONNECTOR_CONTRACT_FAMILIES
        ):
            raise ValueError(
                f"Unsupported contract family '{self.contract_family}'."
            )

        if not self.supported_environments:
            raise ValueError(
                f"Connector '{self.connector_id}' must declare environments."
            )

        if len(set(self.supported_environments)) != len(
            self.supported_environments
        ):
            raise ValueError(
                f"Connector '{self.connector_id}' has duplicate "
                f"environments."
            )

        unsupported_environments = set(
            self.supported_environments
        ).difference(SUPPORTED_CONNECTOR_ENVIRONMENTS)

        if unsupported_environments:
            raise ValueError(
                f"Connector '{self.connector_id}' has unsupported "
                f"environments: {sorted(unsupported_environments)}."
            )

        if "sandbox" not in self.supported_environments:
            raise ValueError(
                f"Connector '{self.connector_id}' must declare sandbox."
            )

        if not self.requires_enterprise_review:
            raise ValueError(
                f"Connector '{self.connector_id}' must require "
                f"Enterprise review."
            )

        if not self.requires_sandbox_before_production:
            raise ValueError(
                f"Connector '{self.connector_id}' must require sandbox "
                f"before production."
            )

        disabled_flags = (
            "read_allowed",
            "write_allowed",
            "runtime_enabled",
            "external_http_enabled",
            "production_allowed",
            "automatic_activation_allowed",
            "credentials_storage_allowed",
            "raw_secret_visible",
        )

        for field_name in disabled_flags:
            if getattr(self, field_name):
                raise ValueError(
                    f"Connector '{self.connector_id}' cannot set "
                    f"{field_name}=True in 16A."
                )

        adapter_contract = get_adapter_contract(
            self.adapter_contract_id
        )

        if adapter_contract.runtime_connector_approved:
            raise ValueError(
                f"Adapter contract '{adapter_contract.contract_id}' "
                f"must remain non-runtime."
            )

        if not self.capabilities:
            raise ValueError(
                f"Connector '{self.connector_id}' must declare capabilities."
            )

        capability_ids = tuple(
            capability.capability_id
            for capability in self.capabilities
        )

        if len(set(capability_ids)) != len(capability_ids):
            raise ValueError(
                f"Connector '{self.connector_id}' has duplicate "
                f"capabilities."
            )

        for capability in self.capabilities:
            if capability.scope_id not in adapter_contract.all_scopes:
                raise ValueError(
                    f"Capability '{capability.capability_id}' references "
                    f"scope '{capability.scope_id}' outside adapter "
                    f"contract '{adapter_contract.contract_id}'."
                )

            if (
                capability.access_mode == "read"
                and capability.scope_id
                not in adapter_contract.required_scopes
            ):
                raise ValueError(
                    f"Read capability '{capability.capability_id}' must "
                    f"use a required read scope."
                )

            if (
                capability.access_mode == "write"
                and capability.scope_id
                not in adapter_contract.optional_write_scopes
            ):
                raise ValueError(
                    f"Write capability '{capability.capability_id}' must "
                    f"use an optional write scope."
                )

            if (
                capability.access_mode == "restricted"
                and capability.scope_id
                not in adapter_contract.restricted_scopes
            ):
                raise ValueError(
                    f"Restricted capability "
                    f"'{capability.capability_id}' must use a restricted "
                    f"scope."
                )

        if not self.authentication_profile_ids:
            raise ValueError(
                f"Connector '{self.connector_id}' must reference an "
                f"authentication profile."
            )

        if len(set(self.authentication_profile_ids)) != len(
            self.authentication_profile_ids
        ):
            raise ValueError(
                f"Connector '{self.connector_id}' has duplicate "
                f"authentication profiles."
            )

        for profile_id in self.authentication_profile_ids:
            profile = get_credential_profile(profile_id)

            if self.adapter_contract_id not in (
                profile.adapter_contract_ids
            ):
                raise ValueError(
                    f"Authentication profile '{profile_id}' does not "
                    f"cover adapter contract "
                    f"'{self.adapter_contract_id}'."
                )

            if (
                profile.approved_for_runtime
                or profile.runtime_connector_approved
            ):
                raise ValueError(
                    f"Authentication profile '{profile_id}' must remain "
                    f"non-runtime."
                )

        if not self.data_classifications:
            raise ValueError(
                f"Connector '{self.connector_id}' must classify its data."
            )

        if len(set(self.data_classifications)) != len(
            self.data_classifications
        ):
            raise ValueError(
                f"Connector '{self.connector_id}' has duplicate data "
                f"classifications."
            )

        unsupported_classifications = set(
            self.data_classifications
        ).difference(SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS)

        if unsupported_classifications:
            raise ValueError(
                f"Connector '{self.connector_id}' has unsupported data "
                f"classifications: "
                f"{sorted(unsupported_classifications)}."
            )

    @property
    def capability_ids(self) -> tuple[str, ...]:
        """Return capability ids in stable order."""

        return tuple(
            capability.capability_id
            for capability in self.capabilities
        )

    @property
    def read_capabilities(
        self,
    ) -> tuple[ConnectorCapability, ...]:
        """Return declared read capabilities."""

        return tuple(
            capability
            for capability in self.capabilities
            if capability.access_mode == "read"
        )

    @property
    def write_capabilities(
        self,
    ) -> tuple[ConnectorCapability, ...]:
        """Return declared write capabilities."""

        return tuple(
            capability
            for capability in self.capabilities
            if capability.access_mode == "write"
        )

    @property
    def restricted_capabilities(
        self,
    ) -> tuple[ConnectorCapability, ...]:
        """Return declared restricted capabilities."""

        return tuple(
            capability
            for capability in self.capabilities
            if capability.access_mode == "restricted"
        )


__all__ = [
    "SUPPORTED_CONNECTOR_CONTRACT_FAMILIES",
    "SUPPORTED_CONNECTOR_DATA_CLASSIFICATIONS",
    "SUPPORTED_CONNECTOR_ENVIRONMENTS",
    "ConnectorCapability",
    "ConnectorCapabilityAccess",
    "ConnectorContractFamily",
    "ConnectorRuntimeContract",
    "normalize_runtime_connector_id",
]
