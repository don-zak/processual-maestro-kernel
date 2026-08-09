"""Client-safe Enterprise Integration console contract for Settings.

This route extension composes existing authoritative plan capability, API-key,
operational-profile, scope-catalog, and declarative readiness primitives into
one payload for the client Settings surface. It does not issue credentials,
call external services, approve production connectors, or expose stored secrets.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import Depends

from processual_api.auth.security import get_current_user
from processual_api.billing.usage_pricing import enterprise_integration_capability
from processual_api.integrations.integration_readiness import (
    list_integration_readiness_checks,
    summarize_integration_readiness,
)
from processual_api.integrations.scope_catalog import list_integration_scopes

from . import settings as settings_module


def _identity(current_user: dict[str, Any]) -> tuple[str, str]:
    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or "default"
    )
    client_id = str(current_user.get("client_id") or user_id)
    return user_id, client_id


def _safe_readiness_checks(checks: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "readiness_check_id": check.readiness_check_id,
            "contract_id": check.contract_id,
            "credential_profile_id": check.credential_profile_id,
            "status": check.status,
            "blocking_reasons": list(check.blocking_reasons),
            "next_action": check.next_action,
            "sandbox_ready": check.sandbox_ready,
            "production_allowed": False,
            "runtime_connector_approved": False,
        }
        for check in checks
    ]


def _scope_posture(*, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "total": 0,
            "read": 0,
            "write": 0,
            "restricted": 0,
            "read_only_pilot": 0,
            "supervisor_approval_required": 0,
            "production_allowed_without_approval": 0,
        }

    scopes = list_integration_scopes()
    by_access = Counter(scope.access_level for scope in scopes)
    return {
        "enabled": True,
        "total": len(scopes),
        "read": by_access.get("read", 0),
        "write": by_access.get("write", 0),
        "restricted": by_access.get("restricted", 0),
        "read_only_pilot": sum(
            1 for scope in scopes if scope.allowed_in_read_only_pilot
        ),
        "supervisor_approval_required": sum(
            1 for scope in scopes if scope.requires_supervisor_approval
        ),
        "production_allowed_without_approval": sum(
            1 for scope in scopes if scope.production_allowed_without_approval
        ),
    }


def _console_sections(
    *,
    enabled: bool,
    key_count: int,
    operational_profile_count: int,
    scope_posture: dict[str, Any],
    readiness: dict[str, int],
) -> list[dict[str, Any]]:
    if not enabled:
        return [
            {
                "id": "entitlement",
                "label": "Enterprise entitlement",
                "status": "locked",
                "next_action": "Upgrade to an eligible Enterprise Integration plan.",
            },
        ]

    keys_status = "ready" if key_count > 0 else "action_required"
    profile_status = (
        "ready"
        if operational_profile_count > 0 and int(scope_posture.get("total", 0)) > 0
        else "action_required"
    )
    sandbox_ready = int(readiness.get("sandbox_ready", 0))
    readiness_status = "ready" if sandbox_ready > 0 else "action_required"

    return [
        {
            "id": "entitlement",
            "label": "Enterprise entitlement",
            "status": "ready",
            "next_action": "Review integration credentials and sandbox readiness.",
        },
        {
            "id": "api_keys",
            "label": "API & service identity",
            "status": keys_status,
            "next_action": (
                "Review active integration keys."
                if key_count > 0
                else "Provision a sandbox integration key or request supervised issuance."
            ),
        },
        {
            "id": "integration_profile",
            "label": "Profiles & scope posture",
            "status": profile_status,
            "next_action": (
                "Review read, write, and restricted scope posture before sandbox use."
                if profile_status == "ready"
                else "Complete the integration profile and scope policy before sandbox use."
            ),
        },
        {
            "id": "readiness",
            "label": "Integration readiness",
            "status": readiness_status,
            "next_action": (
                "Proceed with supervised sandbox review."
                if sandbox_ready > 0
                else "Complete required customer inputs and security controls."
            ),
        },
        {
            "id": "production",
            "label": "Production approval",
            "status": "blocked",
            "next_action": "Production remains blocked until supervised qualification is complete.",
        },
    ]


def _next_action(
    *,
    enabled: bool,
    key_count: int,
    operational_profile_count: int,
    readiness: dict[str, int],
) -> str:
    if not enabled:
        return "Upgrade to an eligible Enterprise Integration plan."
    if key_count == 0:
        return "Provision a sandbox integration key or request supervised issuance."
    if operational_profile_count == 0:
        return "Complete the integration profile and scope policy before sandbox use."
    if int(readiness.get("sandbox_ready", 0)) == 0:
        return "Complete required integration inputs and security controls."
    return "Proceed to supervised sandbox review; production remains blocked."


def enterprise_integration_console_payload(
    *,
    current_user: dict[str, Any],
) -> dict[str, Any]:
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    plan_id = settings_module._resolve_client_api_key_integration_plan_id(
        user_id,
        raw,
        current_user,
    )
    capability = enterprise_integration_capability(plan_id)
    enabled = bool(capability["enabled"])

    keys = (
        settings_module._active_client_integration_keys(raw, client_id)
        if enabled
        else []
    )
    operational = settings_module._client_api_key_operational_profiles_payload(
        enabled=enabled
    )
    scope_posture = _scope_posture(enabled=enabled)
    readiness_source = list_integration_readiness_checks() if enabled else []
    readiness_checks = _safe_readiness_checks(readiness_source)
    readiness = (
        summarize_integration_readiness(readiness_source)
        if enabled
        else {
            "total": 0,
            "blocked": 0,
            "sandbox_ready": 0,
            "production_allowed": 0,
            "runtime_connector_approved": 0,
        }
    )

    key_count = len(keys)
    operational_profile_count = int(operational["operational_profile_count"])
    return {
        "enabled": enabled,
        "status": capability["status"],
        "plan_id": capability["plan_id"],
        "normalized_plan_id": capability["normalized_plan_id"],
        "canonical_plan_id": capability.get(
            "canonical_plan_id", capability["normalized_plan_id"]
        ),
        "legacy_compatibility": capability["legacy_compatibility"],
        "eligible_plans": capability["eligible_plans"],
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
        "key_count": key_count,
        "keys": keys,
        "operational_profiles_enabled": operational[
            "operational_profiles_enabled"
        ],
        "operational_profile_count": operational_profile_count,
        "operational_profiles": operational["operational_profiles"],
        "scope_posture": scope_posture,
        "readiness": readiness,
        "readiness_checks": readiness_checks,
        "sections": _console_sections(
            enabled=enabled,
            key_count=key_count,
            operational_profile_count=operational_profile_count,
            scope_posture=scope_posture,
            readiness=readiness,
        ),
        "next_action": _next_action(
            enabled=enabled,
            key_count=key_count,
            operational_profile_count=operational_profile_count,
            readiness=readiness,
        ),
    }


@settings_module.router.get("/enterprise-integration", response_model=dict)
async def get_enterprise_integration_console(
    current_user: dict = Depends(get_current_user),
):
    return enterprise_integration_console_payload(current_user=current_user)


__all__ = [
    "enterprise_integration_console_payload",
    "get_enterprise_integration_console",
]
