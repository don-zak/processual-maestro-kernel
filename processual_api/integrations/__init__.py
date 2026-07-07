"""Integration readiness primitives for external adapters."""

from processual_api.integrations.sector_profiles import (
    INTEGRATION_SECTOR_PROFILES,
    SUPPORTED_SECTORS,
    SectorAdapterProfile,
    get_sector_profile,
    list_sector_profiles,
)

__all__ = [
    "INTEGRATION_SECTOR_PROFILES",
    "SUPPORTED_SECTORS",
    "SectorAdapterProfile",
    "get_sector_profile",
    "list_sector_profiles",
]
