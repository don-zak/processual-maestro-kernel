"""Client-safe provider status alias used by the Settings Operations Center."""

from fastapi import Depends

from processual_api.auth.security import get_current_user

from . import settings as settings_module


@settings_module.router.get("/client/provider-connection", response_model=dict)
async def get_client_provider_connection_alias(
    current_user: dict = Depends(get_current_user),
):
    return await settings_module.get_provider_connection(current_user)
