from __future__ import annotations

import pytest

from processual_api.routers import evaluation_runtime_scenarios as scenarios_runtime


@pytest.mark.asyncio
async def test_status_enrichment_returns_only_sealed_grant_scenarios(monkeypatch) -> None:
    async def fake_status(current_user):
        return {
            "credential_status": "active",
            "grant_id": "eval_test",
            "api_key_id": "evalkey_test",
            "quota": {"limit": 100, "used": 0, "remaining": 100},
            "production_allowed": False,
        }

    async def fake_load(owner_id: str):
        assert owner_id == "owner-1"
        return {
            "evaluation_grants_v1": [
                {
                    "grant_id": "eval_test",
                    "allowed_task_ids": ["crm.customer_context"],
                    "allowed_binding_ids": ["crm.context.eval"],
                    "allowed_endpoints": [
                        {
                            "method": "POST",
                            "path": "/evaluation/runtime/task-execute",
                        }
                    ],
                }
            ],
            "enterprise_endpoint_bindings_v1": [
                {
                    "binding_id": "crm.context.eval",
                    "task_id": "crm.customer_context",
                },
                {
                    "binding_id": "billing.unrelated",
                    "task_id": "billing.account_context",
                },
            ],
        }

    monkeypatch.setattr(scenarios_runtime, "evaluation_runtime_status", fake_status)
    monkeypatch.setattr(scenarios_runtime, "load_evaluation_authority_state", fake_load)

    payload = await scenarios_runtime.evaluation_runtime_status_with_scenarios(
        {
            "sub": "owner-1",
            "evaluation_grant_id": "eval_test",
            "api_key_id": "evalkey_test",
        }
    )

    assert payload["guided_scenario_count"] == 1
    scenario = payload["guided_scenarios"][0]
    assert scenario["scenario_id"] == "CRM-CONTEXT-01"
    assert scenario["task_id"] == "crm.customer_context"
    assert scenario["binding_ids"] == ["crm.context.eval"]
    assert scenario["runnable"] is True
    assert payload["scenario_catalog_source"] == "sealed_evaluation_grant"
    assert payload["scenario_status_reads_consume_quota"] is False
    assert payload["raw_scenario_input_persisted"] is False
    assert payload["production_allowed"] is False


@pytest.mark.asyncio
async def test_status_enrichment_fails_closed_without_evaluation_identity(monkeypatch) -> None:
    async def fake_status(current_user):
        return {"credential_status": "active"}

    monkeypatch.setattr(scenarios_runtime, "evaluation_runtime_status", fake_status)

    with pytest.raises(Exception) as exc_info:
        await scenarios_runtime.evaluation_runtime_status_with_scenarios({})

    assert getattr(exc_info.value, "status_code", None) == 403
    assert getattr(exc_info.value, "detail", "") == "Governed Evaluation credential required."
