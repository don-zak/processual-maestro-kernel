"""Operational profiles dedicated to platform runtime API-key access."""

from __future__ import annotations

from copy import deepcopy

_PLATFORM_PROFILES: tuple[dict[str, object], ...] = (
    {
        "profile_id": "platform_runtime_observability",
        "display_name": "Platform Runtime Observability",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "read:health",
            "read:adapters",
            "read:governor",
            "read:reports",
        ),
        "forbidden_scopes": (
            "run:analyze",
            "run:govern",
            "admin:*",
            "production_write",
            "connector_runtime:execute",
        ),
        "read_only": True,
        "write_allowed": False,
        "restricted_allowed": False,
        "requires_enterprise_plan": False,
        "requires_integration_readiness": False,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Use for sandbox runtime visibility without execution authority.",
    },
    {
        "profile_id": "platform_governor_sandbox",
        "display_name": "Platform Governor Sandbox",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": (
            "read:governor",
            "read:reports",
            "run:analyze",
            "run:govern",
        ),
        "forbidden_scopes": (
            "admin:*",
            "production_write",
            "connector_runtime:execute",
        ),
        "read_only": False,
        "write_allowed": True,
        "restricted_allowed": False,
        "requires_enterprise_plan": False,
        "requires_integration_readiness": False,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": "Use only for governed sandbox CGT and governor execution.",
    },
    {
        "profile_id": "platform_evaluation_runtime",
        "display_name": "Platform External Evaluation Runtime",
        "base_key_profile": "service_integration",
        "client_visible": True,
        "environment": "sandbox",
        "allowed_scopes": ("run:evaluation",),
        "forbidden_scopes": (
            "admin:*",
            "production_write",
            "connector_runtime:execute",
        ),
        "read_only": False,
        "write_allowed": True,
        "restricted_allowed": False,
        "requires_enterprise_plan": False,
        "requires_integration_readiness": True,
        "requires_supervisor_for_write": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": (
            "Use only with a prepared External Evaluation binding, sandbox grant, "
            "and verified transport."
        ),
    },
)


def list_platform_api_key_operational_profiles() -> tuple[dict[str, object], ...]:
    return tuple(deepcopy(profile) for profile in _PLATFORM_PROFILES)


__all__ = ["list_platform_api_key_operational_profiles"]
