from processual_api.services.evaluation_scenarios import customer_evaluation_scenarios


def _grant(*, endpoints=None, bindings=None, tasks=None):
    return {
        "allowed_task_ids": tasks or ["crm.customer_context"],
        "allowed_binding_ids": bindings or [],
        "allowed_endpoints": endpoints or [{"method": "POST", "path": "/cgt/govern"}],
    }


def test_scenario_never_widens_grant_authority() -> None:
    raw = {
        "enterprise_endpoint_bindings_v1": [
            {
                "binding_id": "crm.context.eval",
                "task_id": "crm.customer_context",
            }
        ]
    }
    scenarios = customer_evaluation_scenarios(raw, _grant())
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario["scenario_id"] == "CRM-CONTEXT-01"
    assert scenario["runnable"] is False
    assert scenario["readiness"] == "runtime_endpoint_required"
    assert scenario["binding_ids"] == []
    assert scenario["production_allowed"] is False
    assert scenario["raw_secret_visible"] is False


def test_scenario_is_runnable_only_with_sealed_runtime_endpoint_and_matching_binding() -> None:
    raw = {
        "enterprise_endpoint_bindings_v1": [
            {
                "binding_id": "crm.context.eval",
                "task_id": "crm.customer_context",
            },
            {
                "binding_id": "billing.unrelated",
                "task_id": "billing.account_context",
            },
        ]
    }
    grant = _grant(
        endpoints=[{"method": "POST", "path": "/evaluation/runtime/task-execute"}],
        bindings=["crm.context.eval", "billing.unrelated"],
    )
    scenario = customer_evaluation_scenarios(raw, grant)[0]
    assert scenario["runnable"] is True
    assert scenario["readiness"] == "ready"
    assert scenario["binding_ids"] == ["crm.context.eval"]
    assert scenario["quota_cost_new_execution"] == 1
    assert scenario["quota_cost_replay"] == 0


def test_scenario_catalog_exposes_only_tasks_sealed_into_grant() -> None:
    raw = {"enterprise_endpoint_bindings_v1": []}
    grant = _grant(tasks=["crm.customer_state_summary"])
    scenarios = customer_evaluation_scenarios(raw, grant)
    assert [item["task_id"] for item in scenarios] == ["crm.customer_state_summary"]
    assert all("api_key" not in item for item in scenarios)
    assert all("secret" not in item for item in scenarios)
