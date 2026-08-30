from __future__ import annotations

from processual_api.integrations.api_key_access_policy import (
    get_api_key_access_policy,
)
from processual_api.integrations.api_key_platform_operational_profiles import (
    list_platform_api_key_operational_profiles,
)
from processual_api.services.evaluation_coverage_plan import (
    build_evaluation_coverage_plan,
)


def test_every_campaign_is_issuable_under_its_declared_profile() -> None:
    profiles = {
        str(profile["profile_id"]): profile
        for profile in list_platform_api_key_operational_profiles()
    }
    plan = build_evaluation_coverage_plan()

    for campaign in plan["campaigns"]:
        profile_id = campaign["operational_profile_id"]
        profile = profiles[profile_id]
        allowed_scopes = {str(scope) for scope in profile["allowed_scopes"]}
        forbidden_scopes = {str(scope) for scope in profile["forbidden_scopes"]}
        campaign_scopes = set(campaign["required_scopes"])

        assert campaign_scopes
        assert campaign_scopes.issubset(allowed_scopes)
        assert campaign_scopes.isdisjoint(forbidden_scopes)
        assert profile["production_allowed"] is False
        assert profile["runtime_connector_approved"] is False

        for endpoint in campaign["endpoints"]:
            policy = get_api_key_access_policy(
                endpoint["method"],
                endpoint["path"],
            )
            assert policy is not None
            assert profile_id in policy.operational_profile_ids
            assert set(policy.required_scopes).issubset(campaign_scopes)


def test_real_task_campaign_does_not_inherit_governor_or_observability_scopes() -> None:
    plan = build_evaluation_coverage_plan()
    evaluation = next(
        campaign
        for campaign in plan["campaigns"]
        if campaign["operational_profile_id"] == "platform_evaluation_runtime"
    )

    assert evaluation["required_scopes"] == ["run:evaluation"]
    assert evaluation["endpoint_count"] == 1
    assert evaluation["endpoints"] == [
        {
            "method": "POST",
            "path": "/evaluation/runtime/task-execute",
            "task_id": "platform.evaluation.task_execute",
            "capability": "Bounded canonical task execution for Evaluation Runtime",
            "operation_class": "execute",
            "required_scopes": ["run:evaluation"],
            "production_allowed": False,
        }
    ]
