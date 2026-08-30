from __future__ import annotations

import asyncio

from processual_api.integrations.api_key_access_policy import (
    list_api_key_access_policies,
)
from processual_api.routers import settings_admin_evaluation_coverage as coverage_route
from processual_api.services.evaluation_coverage_plan import (
    build_evaluation_coverage_plan,
)


def _policy_keys() -> set[tuple[str, str]]:
    return {
        (policy.method, policy.path)
        for policy in list_api_key_access_policies()
    }


def _campaign_keys(plan: dict) -> set[tuple[str, str]]:
    return {
        (endpoint["method"], endpoint["path"])
        for campaign in plan["campaigns"]
        for endpoint in campaign["endpoints"]
    }


def test_coverage_plan_covers_every_policy_endpoint_exactly_once() -> None:
    plan = build_evaluation_coverage_plan()
    policy_keys = _policy_keys()
    campaign_keys = _campaign_keys(plan)

    flattened = [
        (endpoint["method"], endpoint["path"])
        for campaign in plan["campaigns"]
        for endpoint in campaign["endpoints"]
    ]

    assert plan["coverage_model"] == "least_privilege_multi_grant"
    assert plan["complete"] is True
    assert plan["coverage_percent"] == 100
    assert plan["policy_endpoint_count"] == len(policy_keys)
    assert plan["covered_endpoint_count"] == len(policy_keys)
    assert plan["uncovered_endpoints"] == []
    assert campaign_keys == policy_keys
    assert len(flattened) == len(set(flattened))


def test_coverage_plan_separates_observability_governor_and_real_task_keys() -> None:
    plan = build_evaluation_coverage_plan()
    by_profile = {
        campaign["operational_profile_id"]: campaign
        for campaign in plan["campaigns"]
    }

    assert set(by_profile) == {
        "platform_runtime_observability",
        "platform_governor_sandbox",
        "platform_evaluation_runtime",
    }

    observability = by_profile["platform_runtime_observability"]
    governor = by_profile["platform_governor_sandbox"]
    evaluation = by_profile["platform_evaluation_runtime"]

    assert observability["endpoint_count"] == 5
    assert governor["endpoint_count"] == 2
    assert evaluation["endpoint_count"] == 1
    assert evaluation["required_scopes"] == ["run:evaluation"]
    assert evaluation["endpoints"][0]["path"] == "/evaluation/runtime/task-execute"

    for campaign in plan["campaigns"]:
        assert campaign["separate_key_recommended"] is True
        assert campaign["subscription_required"] is False
        assert campaign["production_allowed"] is False


def test_coverage_plan_never_contains_control_plane_endpoint() -> None:
    plan = build_evaluation_coverage_plan()
    for campaign in plan["campaigns"]:
        for endpoint in campaign["endpoints"]:
            assert not endpoint["path"].startswith(("/settings", "/admin", "/auth"))
            assert endpoint["production_allowed"] is False


def test_coverage_plan_route_requires_super_admin_authority(monkeypatch) -> None:
    observed: list[dict] = []

    async def _authority(current_user: dict) -> None:
        observed.append(current_user)

    monkeypatch.setattr(
        coverage_route,
        "require_active_platform_admin",
        _authority,
    )
    current_user = {
        "sub": "evaluation-owner",
        "session_type": "identity_user",
    }

    result = asyncio.run(
        coverage_route.evaluation_coverage_plan(current_user=current_user)
    )

    assert observed == [current_user]
    assert result["complete"] is True
    assert result["coverage_percent"] == 100
    assert result["super_admin_provisions_keys"] is True
    assert result["tester_provisions_keys"] is False
