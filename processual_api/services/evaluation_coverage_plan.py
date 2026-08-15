"""Build a least-privilege campaign plan that covers every grantable runtime endpoint.

The plan is deterministic and intentionally separates observability, governor
execution, and real canonical task execution. A full evaluation campaign may
therefore use multiple bounded grants/keys instead of one unnecessarily broad
credential while still proving coverage of the complete API-key runtime policy.
All grants that belong to one external-program campaign should reuse the same
``client_id`` so their runtime evidence can be aggregated without widening any
single credential.
"""

from __future__ import annotations

from typing import Any

from processual_api.integrations.api_key_access_policy import (
    ApiKeyAccessPolicy,
    list_api_key_access_policies,
)

_PROFILE_ORDER = (
    "platform_runtime_observability",
    "platform_governor_sandbox",
    "platform_evaluation_runtime",
)


def _preferred_profile(policy: ApiKeyAccessPolicy) -> str:
    profiles = set(policy.operational_profile_ids)
    for profile_id in _PROFILE_ORDER:
        if profile_id in profiles:
            return profile_id
    return sorted(profiles)[0]


def build_evaluation_coverage_plan() -> dict[str, Any]:
    policies = list_api_key_access_policies()
    groups: dict[str, list[ApiKeyAccessPolicy]] = {}
    for policy in policies:
        profile_id = _preferred_profile(policy)
        groups.setdefault(profile_id, []).append(policy)

    campaigns: list[dict[str, Any]] = []
    covered: set[tuple[str, str]] = set()
    for profile_id in _PROFILE_ORDER:
        profile_policies = groups.get(profile_id, [])
        if not profile_policies:
            continue
        endpoints = [
            {
                "method": policy.method,
                "path": policy.path,
                "task_id": policy.task_id,
                "capability": policy.capability,
                "operation_class": policy.operation_class,
                "required_scopes": list(policy.required_scopes),
                "production_allowed": False,
            }
            for policy in profile_policies
        ]
        scopes = sorted(
            {
                scope
                for policy in profile_policies
                for scope in policy.required_scopes
            }
        )
        covered.update((policy.method, policy.path) for policy in profile_policies)
        campaigns.append(
            {
                "campaign_id": f"evaluation-{profile_id}",
                "operational_profile_id": profile_id,
                "endpoint_count": len(endpoints),
                "endpoints": endpoints,
                "required_scopes": scopes,
                "separate_key_recommended": True,
                "reuse_campaign_client_id": True,
                "subscription_required": False,
                "production_allowed": False,
            }
        )

    all_policy_keys = {(policy.method, policy.path) for policy in policies}
    uncovered = sorted(all_policy_keys - covered)
    return {
        "coverage_model": "least_privilege_multi_grant",
        "campaign_correlation": "client_id",
        "campaign_client_id_requirement": (
            "Use one unique client_id for the external evaluation campaign and "
            "reuse it across the bounded grants/keys in this plan."
        ),
        "policy_endpoint_count": len(all_policy_keys),
        "covered_endpoint_count": len(covered),
        "coverage_percent": 100 if covered == all_policy_keys else 0,
        "complete": covered == all_policy_keys,
        "campaign_count": len(campaigns),
        "campaigns": campaigns,
        "uncovered_endpoints": [
            {"method": method, "path": path}
            for method, path in uncovered
        ],
        "super_admin_provisions_keys": True,
        "tester_provisions_keys": False,
        "subscription_required": False,
        "production_allowed": False,
    }


__all__ = ["build_evaluation_coverage_plan"]
