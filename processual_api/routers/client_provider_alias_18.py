"""Deprecated client-safe provider status alias for compatibility only.

The current Settings UI uses ``/settings/provider-connection`` directly. Keep
this alias temporarily for external clients while the compatibility surface is
retired in a later isolated cleanup.
"""

from fastapi import Depends, Response

from processual_api.auth.security import get_current_user

from . import settings as settings_module


@settings_module.router.get(
    "/client/provider-connection",
    response_model=dict,
    deprecated=True,
)
async def get_client_provider_connection_alias(
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    response.headers["Deprecation"] = "true"
    response.headers["X-Maestro-Replacement"] = "/settings/provider-connection"
    return await settings_module.get_provider_connection(current_user)
