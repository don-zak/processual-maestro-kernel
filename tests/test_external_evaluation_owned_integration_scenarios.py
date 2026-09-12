from __future__ import annotations

from pathlib import Path

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    validate_endpoint_binding,
)
from processual_api.routers import settings_admin_evaluation_owned_integration_scenarios as routes
from processual_api.services.evaluation_grants import EVALUATION_TASK_EXECUTE_ENDPOINT
from processual_api.services.evaluation_scenarios import customer_evaluation_scenarios

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "deployment" / "evaluation-owned-sandbox" / "cloudflare" / "worker.js"
ROUTES = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_owned_integration_scenarios.py"


def _body() -> routes.OwnedIntegrationBillingPresetRequest:
    return routes.OwnedIntegrationBillingPresetRequest(
        base_url="https://processual-maestro-evaluation-sandbox.zaksam2030.workers.dev"
    )


def _grant(*, include_binding: bool = True, include_runtime: bool = True) -> dict:
    return {
        "evaluation_type": "integration",
        "allowed_task_ids": ["billing.account_context"],
        "allowed_binding_ids": (
            ["evaluation.integration.billing_account_context.owned"]
            if include_binding
            else []
        ),
        "allowed_endpoints": (
            [{"method": EVALUATION_TASK_EXECUTE_ENDPOINT[0], "path": EVALUATION_TASK_EXECUTE_ENDPOINT[1]}]
            if include_runtime
            else []
        ),
    }


def test_owned_integration_billing_binding_is_safe_read_and_schema_valid() -> None:
    binding = routes._binding(_body())
    validation = validate_endpoint_binding(binding)

    assert binding.binding_id == "evaluation.integration.billing_account_context.owned"
    assert binding.adapter_contract_id == "billing"
    assert binding.task_id == "billing.account_context"
    assert binding.method == "GET"
    assert binding.path == "/billing/accounts/1"
    assert binding.required_scope_ids == ["billing:read"]
    assert validation["operation_class"] == "read"
    assert validation["environment"] == "sandbox"
    assert validation["production_allowed"] is False
    assert validation["runtime_connector_approved"] is False


def test_integration_scenario_stays_locked_without_prepared_binding() -> None:
    scenarios = customer_evaluation_scenarios({}, _grant(include_binding=False))

    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario["scenario_id"] == "INT-BILLING-01"
    assert scenario["task_id"] == "billing.account_context"
    assert scenario["runnable"] is False
    assert scenario["readiness"] == "prepared_binding_required"
    assert scenario["production_allowed"] is False


def test_integration_scenario_becomes_runnable_only_inside_sealed_binding_authority() -> None:
    binding = routes._binding(_body())
    raw = {BINDING_STORAGE_KEY: [binding.model_dump(mode="json")]}
    scenarios = customer_evaluation_scenarios(raw, _grant())

    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario["scenario_id"] == "INT-BILLING-01"
    assert scenario["runnable"] is True
    assert scenario["readiness"] == "ready"
    assert scenario["binding_ids"] == [binding.binding_id]
    assert scenario["quota_cost_new_execution"] == 1
    assert scenario["quota_cost_replay"] == 0
    assert scenario["raw_secret_visible"] is False


def test_integration_scenario_requires_runtime_task_execute_endpoint() -> None:
    binding = routes._binding(_body())
    raw = {BINDING_STORAGE_KEY: [binding.model_dump(mode="json")]}
    scenario = customer_evaluation_scenarios(raw, _grant(include_runtime=False))[0]

    assert scenario["runnable"] is False
    assert scenario["readiness"] == "runtime_endpoint_required"


def test_integration_preset_recommends_200_unit_subscription_free_grant() -> None:
    source = ROUTES.read_text(encoding="utf-8")

    assert '"evaluation_type": "integration"' in source
    assert '"quota": 200' in source
    assert '"subscription_required": False' in source
    assert '"production_allowed": False' in source
    assert '"operation_class": "read"' in source
    assert '"production_mutation_performed": False' in source


def test_project_owned_worker_exposes_read_only_billing_fixture() -> None:
    source = WORKER.read_text(encoding="utf-8")

    assert "const BILLING_ACCOUNT = Object.freeze" in source
    assert "'/billing/accounts/1'" in source
    assert "account_id: 'sandbox-account-001'" in source
    assert "invoice_status: 'current'" in source
    assert "payment_status: 'paid'" in source
    assert "production_allowed: false" in source
    assert "if (!['GET', 'HEAD'].includes(method))" in source
