"""Admin-safe API key provisioning catalogs."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from processual_api.auth.security import get_current_user
from processual_api.integrations.api_key_access_policy import get_api_key_access_policy
from processual_api.integrations.api_key_operational_profiles import (
    api_key_operational_profiles_payload,
)
from processual_api.integrations.api_key_platform_operational_profiles import (
    list_platform_api_key_operational_profiles,
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


def _route_catalog(request: Request) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for route in request.app.routes:
        path = str(getattr(route, "path", "") or "")
        if not path.startswith("/"):
            continue
        methods = sorted(
            method
            for method in (getattr(route, "methods", None) or set())
            if method not in {"HEAD", "OPTIONS"}
        )
        if not methods:
            continue
        tags = [str(tag) for tag in (getattr(route, "tags", None) or [])]
        route_name = str(getattr(route, "name", "") or "")
        for method in methods:
            policy = get_api_key_access_policy(method, path)
            control_plane = path.startswith(("/settings", "/admin", "/auth"))
            docs_surface = path in {"/docs", "/redoc", "/openapi.json"}
            grantable = policy is not None and not control_plane and not docs_surface
            rows.append(
                {
                    "method": method,
                    "path": path,
                    "name": route_name,
                    "tags": tags,
                    "capability": (
                        policy.capability
                        if policy
                        else route_name.replace("_", " ").strip() or path
                    ),
                    "task_id": policy.task_id if policy else None,
                    "operation_class": policy.operation_class if policy else None,
                    "required_scopes": list(policy.required_scopes) if policy else [],
                    "operational_profile_ids": (
                        list(policy.operational_profile_ids) if policy else []
                    ),
                    "grantable": grantable,
                    "control_plane": control_plane,
                    "production_allowed": policy.production_allowed if grantable else None,
                    "selection_reason": (
                        "canonical_runtime_access_policy"
                        if grantable
                        else "visibility_only_not_in_grant_policy"
                    ),
                }
            )
    return sorted(rows, key=lambda item: (str(item["path"]), str(item["method"])))


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
    profiles = [
        *list(payload.get("profiles") or []),
        *list_platform_api_key_operational_profiles(),
    ]
    return {
        **payload,
        "profile_count": len(profiles),
        "profiles": profiles,
        "selection_authority": "api_key_operational_profiles",
        "profile_sources": [
            "api_key_operational_profiles",
            "platform_runtime_operational_profiles",
        ],
        "raw_secret_visible": False,
        "admin_provisioning_catalog": True,
    }


@settings_module.router.get(
    "/admin/api-key-access-catalog",
    response_model=dict,
)
async def admin_api_key_access_catalog(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Return registered API routes plus the canonical key-grantable subset."""

    _require_api_key_provisioning_admin(current_user)
    endpoints = _route_catalog(request)
    grantable = [endpoint for endpoint in endpoints if endpoint["grantable"]]
    scopes = sorted(
        {
            str(scope)
            for endpoint in grantable
            for scope in endpoint.get("required_scopes", [])
        }
    )
    tasks = sorted(
        {
            str(endpoint["task_id"])
            for endpoint in grantable
            if endpoint.get("task_id")
        }
    )
    profiles = sorted(
        {
            str(profile_id)
            for endpoint in grantable
            for profile_id in endpoint.get("operational_profile_ids", [])
        }
    )
    return {
        "ok": True,
        "catalog": "api_key_access_catalog",
        "selection_authority": "fastapi_route_registry+explicit_runtime_access_policy",
        "policy_authority": "canonical_runtime_access_policy",
        "endpoint_count": len(endpoints),
        "grantable_endpoint_count": len(grantable),
        "grantable_scope_count": len(scopes),
        "grantable_scopes": scopes,
        "canonical_task_count": len(tasks),
        "canonical_tasks": tasks,
        "operational_profile_count": len(profiles),
        "operational_profile_ids": profiles,
        "production_allowed": False,
        "raw_secret_visible": False,
        "endpoints": endpoints,
    }
