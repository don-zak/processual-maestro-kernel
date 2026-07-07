"""Integration readiness primitives for external adapters."""

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
    "INTEGRATION_SCOPE_CATALOG",
    "INTEGRATION_SECTOR_PROFILES",
    "SUPPORTED_INTEGRATION_SCOPES",
    "SUPPORTED_SECTORS",
    "IntegrationScope",
    "SectorAdapterProfile",
    "get_integration_scope",
    "get_sector_profile",
    "is_scope_allowed_in_read_only_pilot",
    "list_integration_scopes",
    "list_scopes_for_sector",
    "list_sector_profiles",
    "scope_requires_supervisor_approval",
]
