"""Immutable registry of disabled future Telecom connector contracts.

The registry contains architecture references only. It does not contain
endpoints, target aliases, secret references, transports, dispatch logic, or
executable connector behavior.
"""

from __future__ import annotations

from types import MappingProxyType

from processual_api.integrations.runtime_contracts import (
    ConnectorCapability,
    ConnectorCapabilityAccess,
    ConnectorRuntimeContract,
    normalize_runtime_connector_id,
)

_TELECOM_AUTHENTICATION_PROFILE = "telecom_operations_api_reference"

_DECLARED_ENVIRONMENTS: tuple[str, ...] = (
    "sandbox",
    "production",
)

_PENDING_EXTERNAL_API_VERSION = "pending_operator_input"


def _capability(
    capability_id: str,
    scope_id: str,
    access_mode: ConnectorCapabilityAccess,
) -> ConnectorCapability:
    """Build a disabled capability with scope-consistent approval posture."""

    return ConnectorCapability(
        capability_id=capability_id,
        scope_id=scope_id,
        access_mode=access_mode,
        approval_required=access_mode != "read",
        sandbox_only=access_mode != "read",
    )


_RUNTIME_CONNECTOR_CONTRACTS: dict[
    str,
    ConnectorRuntimeContract,
] = {
    "telecom_crm_reference": ConnectorRuntimeContract(
        connector_id="telecom_crm_reference",
        display_name="Telecom CRM Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="crm",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "customer.read.minimal",
                "crm:read",
                "read",
            ),
            _capability(
                "customer.update.restricted",
                "customer:update",
                "restricted",
            ),
            _capability(
                "customer.record.update.restricted",
                "customer_record:update",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="telecom-crm-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_billing_reference": ConnectorRuntimeContract(
        connector_id="telecom_billing_reference",
        display_name="Telecom Billing Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="billing",
        contract_family="legacy",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "billing.read.summary",
                "billing:read",
                "read",
            ),
            _capability(
                "billing.adjust.restricted",
                "billing:adjust",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "customer_confidential",
            "subscriber_personal",
            "billing_sensitive",
        ),
        mapping_version="telecom-billing-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_ticketing_reference": ConnectorRuntimeContract(
        connector_id="telecom_ticketing_reference",
        display_name="Telecom Ticketing Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="ticketing",
        contract_family="tm_forum",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "ticket.read",
                "ticket:read",
                "read",
            ),
            _capability(
                "helpdesk.read",
                "helpdesk:read",
                "read",
            ),
            _capability(
                "ticket.create.sandbox",
                "ticket:create",
                "write",
            ),
            _capability(
                "ticket.update.sandbox",
                "ticket:update",
                "write",
            ),
            _capability(
                "helpdesk.create.sandbox",
                "helpdesk:create",
                "write",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="telecom-ticketing-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_order_management_reference": ConnectorRuntimeContract(
        connector_id="telecom_order_management_reference",
        display_name="Telecom Order Management Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="order_management",
        contract_family="tm_forum",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "service.order.plan",
                "order:preview",
                "read",
            ),
            _capability(
                "service.order.create.sandbox",
                "order:create_with_approval",
                "write",
            ),
            _capability(
                "service.order.execute.restricted",
                "order:execute",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "subscriber_personal",
        ),
        mapping_version="telecom-order-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
    "telecom_network_assurance_reference": ConnectorRuntimeContract(
        connector_id="telecom_network_assurance_reference",
        display_name="Telecom Network Assurance Runtime Reference",
        connector_version="1.0.0-draft",
        adapter_contract_id="network_assurance",
        contract_family="proprietary",
        supported_environments=_DECLARED_ENVIRONMENTS,
        capabilities=(
            _capability(
                "network.read",
                "network:read",
                "read",
            ),
            _capability(
                "network.diagnostics.read",
                "network:diagnostics_read",
                "read",
            ),
            _capability(
                "network.write.restricted",
                "network:write",
                "restricted",
            ),
        ),
        authentication_profile_ids=(
            _TELECOM_AUTHENTICATION_PROFILE,
        ),
        data_classifications=(
            "internal",
            "customer_confidential",
            "network_operational",
        ),
        mapping_version="telecom-network-assurance-map-1",
        external_api_version=_PENDING_EXTERNAL_API_VERSION,
    ),
}


for _connector_id, _contract in _RUNTIME_CONNECTOR_CONTRACTS.items():
    if _connector_id != _contract.connector_id:
        raise ValueError(
            f"Registry id '{_connector_id}' does not match "
            f"contract id '{_contract.connector_id}'."
        )


RUNTIME_CONNECTOR_CONTRACTS = MappingProxyType(
    _RUNTIME_CONNECTOR_CONTRACTS
)

SUPPORTED_RUNTIME_CONNECTORS: tuple[str, ...] = tuple(
    RUNTIME_CONNECTOR_CONTRACTS
)


def list_runtime_connector_contracts() -> tuple[
    ConnectorRuntimeContract,
    ...,
]:
    """Return all runtime contracts in stable registry order."""

    return tuple(
        RUNTIME_CONNECTOR_CONTRACTS[connector_id]
        for connector_id in SUPPORTED_RUNTIME_CONNECTORS
    )


def get_runtime_connector_contract(
    connector_id: str,
) -> ConnectorRuntimeContract:
    """Return a runtime connector contract by normalized identifier."""

    normalized_id = normalize_runtime_connector_id(connector_id)

    try:
        return RUNTIME_CONNECTOR_CONTRACTS[normalized_id]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_RUNTIME_CONNECTORS)

        raise KeyError(
            f"Unsupported runtime connector '{connector_id}'. "
            f"Supported connectors: {supported}."
        ) from exc


def list_runtime_connectors_for_adapter(
    adapter_contract_id: str,
) -> tuple[ConnectorRuntimeContract, ...]:
    """Return contracts linked to one declarative adapter contract."""

    normalized_adapter_id = (
        adapter_contract_id.strip().lower().replace("-", "_")
    )

    return tuple(
        contract
        for contract in list_runtime_connector_contracts()
        if contract.adapter_contract_id == normalized_adapter_id
    )


def list_runtime_connectors_for_family(
    contract_family: str,
) -> tuple[ConnectorRuntimeContract, ...]:
    """Return contracts that declare one contract family."""

    normalized_family = (
        contract_family.strip().lower().replace("-", "_")
    )

    return tuple(
        contract
        for contract in list_runtime_connector_contracts()
        if contract.contract_family == normalized_family
    )


def validate_runtime_connector_registry() -> tuple[str, ...]:
    """Return deterministic registry integrity issues."""

    issues: list[str] = []

    if set(RUNTIME_CONNECTOR_CONTRACTS) != set(
        SUPPORTED_RUNTIME_CONNECTORS
    ):
        issues.append(
            "Supported runtime connector ids do not match the registry."
        )

    for connector_id, contract in RUNTIME_CONNECTOR_CONTRACTS.items():
        if connector_id != contract.connector_id:
            issues.append(
                f"Registry id '{connector_id}' does not match contract id."
            )

        if contract.runtime_enabled:
            issues.append(
                f"Connector '{connector_id}' enables runtime."
            )

        if contract.external_http_enabled:
            issues.append(
                f"Connector '{connector_id}' enables external HTTP."
            )

        if contract.production_allowed:
            issues.append(
                f"Connector '{connector_id}' allows production."
            )

        if contract.read_allowed or contract.write_allowed:
            issues.append(
                f"Connector '{connector_id}' allows operations."
            )

    return tuple(issues)


__all__ = [
    "RUNTIME_CONNECTOR_CONTRACTS",
    "SUPPORTED_RUNTIME_CONNECTORS",
    "get_runtime_connector_contract",
    "list_runtime_connector_contracts",
    "list_runtime_connectors_for_adapter",
    "list_runtime_connectors_for_family",
    "validate_runtime_connector_registry",
]
