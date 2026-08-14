"""Admin-safe API key provisioning catalogs."""

from __future__ import annotations

from fastapi import Depends, HTTPException

from processual_api.auth.security import get_current_user
from processual_api.integrations.api_key_operational_profiles import (
    api_key_operational_profiles_payload,
)

from . import settings as settings_module

_ALLOWED_ADMIN_ROLES = {
    "admin",
    "owner_admin",
    "security_admin",
    "ops_admin",
}
_ALLOWED_ADMIN_SCOPES = {
    "*",
    "admin:*",
    "admin:settings",
    "admin:api_keys:read",
    "admin:api_keys:write",
}


def _require_api_key_provisioning_admin(current_user: dict) -> None:
    role = str(
        current_user.get("role")
        or current_user.get("admin_role")
        or ""
    ).strip().lower()
    scopes = {
        str(scope).strip().lower()
        for scope in current_user.get("scopes") or []
        if scope
    }
    if role in _ALLOWED_ADMIN_ROLES or scopes.intersection(_ALLOWED_ADMIN_SCOPES):
        return
    raise HTTPException(
        status_code=403,
        detail="API key provisioning catalog requires administrator authority.",
    )


@settings_module.router.get(
    "/admin/api-key-operational-profiles",
    response_model=dict,
)
async def admin_api_key_operational_profiles(
    current_user: dict = Depends(get_current_user),
):
    """Return safe operational profiles for the admin provisioning workspace."""

    _require_api_key_provisioning_admin(current_user)
    payload = api_key_operational_profiles_payload()
    return {
        **payload,
        "selection_authority": "api_key_operational_profiles",
        "raw_secret_visible": False,
        "admin_provisioning_catalog": True,
    }
