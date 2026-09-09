"""Bind Supervisor Session Keys to canonical platform-admin authority.

The historical Settings routes used ``admin:settings`` scope claims. Modern
platform administrators authenticate through identity sessions and persisted
``platform_admin`` authority instead. Replace only the three supervisor-key
routes while preserving their existing business logic and response contracts.
"""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.routing import APIRoute

from processual_api.auth.platform_admin_authority import require_active_platform_admin
from processual_api.auth.security import get_current_user

from . import settings as settings_module

_CREATE_PATH = "/settings/admin/supervisor-session-keys"
_REVOKE_PATH = "/settings/admin/supervisor-session-keys/{session_key_id}/revoke"

_original_create = settings_module.create_admin_supervisor_session_key
_original_list = settings_module.list_admin_supervisor_session_keys
_original_revoke = settings_module.revoke_admin_supervisor_session_key


def _is_legacy_supervisor_route(route: object) -> bool:
    if not isinstance(route, APIRoute):
        return False
    if route.path == _CREATE_PATH and route.methods.intersection({"GET", "POST"}):
        return True
    return route.path == _REVOKE_PATH and "POST" in route.methods


# The settings router has already registered the legacy endpoints when this
# extension loads. Remove exactly those route objects before registering the
# canonical authority wrappers below. No other Settings route is modified.
settings_module.router.routes[:] = [
    route for route in settings_module.router.routes if not _is_legacy_supervisor_route(route)
]


@settings_module.router.post(
    "/admin/supervisor-session-keys",
    response_model=dict,
    status_code=201,
)
async def create_admin_supervisor_session_key_authoritative(
    payload: settings_module.SupervisorSessionKeyIssueRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user, request=request)
    return await _original_create(payload=payload, current_user=current_user)


@settings_module.router.get(
    "/admin/supervisor-session-keys",
    response_model=dict,
)
async def list_admin_supervisor_session_keys_authoritative(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user, request=request)
    return await _original_list(current_user=current_user)


@settings_module.router.post(
    "/admin/supervisor-session-keys/{session_key_id}/revoke",
    response_model=dict,
)
async def revoke_admin_supervisor_session_key_authoritative(
    session_key_id: str,
    payload: settings_module.SupervisorSessionKeyRevokeRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await require_active_platform_admin(current_user, request=request)
    return await _original_revoke(
        session_key_id=session_key_id,
        payload=payload,
        current_user=current_user,
    )


__all__ = [
    "create_admin_supervisor_session_key_authoritative",
    "list_admin_supervisor_session_keys_authoritative",
    "revoke_admin_supervisor_session_key_authoritative",
]
