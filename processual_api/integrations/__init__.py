"""Integration readiness primitives for external adapters."""

from processual_api.integrations.adapter_contracts import (
    INTEGRATION_ADAPTER_CONTRACTS,
    SUPPORTED_ADAPTER_CONTRACTS,
    IntegrationAdapterContract,
    get_adapter_contract,
    list_adapter_contracts,
    list_adapter_contracts_for_scope,
    list_adapter_contracts_for_sector,
)
from processual_api.integrations.scope_catalog import (
    INTEGRATION_SCOPE_CATALOG,
    SUPPORTED_INTEGRATION_SCOPES,
    IntegrationScope,
    get_integration_scope,
    is_scope_allowed_in_read_only_pilot,
    list_integration_scopes,
    list_scopes_for_sector,
    scope_requires_supervisor_approval,
)
from processual_api.integrations.sector_profiles import (
    INTEGRATION_SECTOR_PROFILES,
    SUPPORTED_SECTORS,
    SectorAdapterProfile,
    get_sector_profile,
    list_sector_profiles,
)

__all__ = [
    "INTEGRATION_ADAPTER_CONTRACTS",
    "INTEGRATION_SCOPE_CATALOG",
    "INTEGRATION_SECTOR_PROFILES",
    "SUPPORTED_ADAPTER_CONTRACTS",
    "SUPPORTED_INTEGRATION_SCOPES",
    "SUPPORTED_SECTORS",
    "IntegrationAdapterContract",
    "IntegrationScope",
    "SectorAdapterProfile",
    "get_adapter_contract",
    "get_integration_scope",
    "get_sector_profile",
    "is_scope_allowed_in_read_only_pilot",
    "list_adapter_contracts",
    "list_adapter_contracts_for_scope",
    "list_adapter_contracts_for_sector",
    "list_integration_scopes",
    "list_scopes_for_sector",
    "list_sector_profiles",
    "scope_requires_supervisor_approval",
]

# INTEGRATION-CREDENTIALS-11D exports begin
from processual_api.integrations.credential_profiles import (
    CredentialProfile,
    get_credential_profile,
    list_credential_profiles,
    validate_credential_profiles,
)

__all__ = [
    *list(globals().get("__all__", ())),
    "CredentialProfile",
    "get_credential_profile",
    "list_credential_profiles",
    "validate_credential_profiles",
]
# INTEGRATION-CREDENTIALS-11D exports end
