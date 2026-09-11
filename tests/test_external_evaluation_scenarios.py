from __future__ import annotations

import pytest

from processual_api.integrations.sandbox_operational_readiness import (
    SandboxContentContract,
    safe_content_projection,
)
from processual_api.routers import evaluation_runtime_scenarios as scenarios_runtime
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


def test_project_owned_sandbox_content_is_explicit_and_customer_safe() -> None:
    contract = SandboxContentContract(
        binding_id="evaluation.crm.public",
        dataset_reference="project-evaluation-sandbox-customer-v1",
        fixture_profile_reference="crm-context-read-only-v1",
        required_record_types=("crm_customer",),
        acceptance_criteria_references=("CRM-CONTEXT-01",),
        customer_owned=False,
        project_owned=True,
        synthetic_or_nonproduction=True,
        secrets_included=False,
        raw_payloads_included=False,
    )

    safe = safe_content_projection(contract)
    assert safe["customer_owned"] is False
    assert safe["project_owned"] is True
    assert safe["content_owner"] == "project"
    assert safe["synthetic_or_nonproduction"] is True
    assert safe["secrets_included"] is False
    assert safe["raw_payloads_included"] is False
    assert safe["production_allowed"] is False


def test_sandbox_content_requires_exactly_one_owned_source() -> None:
    common = {
        "binding_id": "evaluation.crm.public",
        "dataset_reference": "evaluation-dataset",
        "fixture_profile_reference": "evaluation-fixture",
        "required_record_types": ("crm_customer",),
        "acceptance_criteria_references": ("CRM-CONTEXT-01",),
    }

    with pytest.raises(ValueError, match="exactly one"):
        SandboxContentContract(
            **common,
            customer_owned=True,
            project_owned=True,
        )

    with pytest.raises(ValueError, match="exactly one"):
        SandboxContentContract(
            **common,
            customer_owned=False,
            project_owned=False,
        )


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
