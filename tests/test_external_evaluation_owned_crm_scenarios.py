from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.requests import Request

from processual_api.integrations.enterprise_endpoint_bindings import (
    BINDING_STORAGE_KEY,
    validate_endpoint_binding,
)
from processual_api.integrations.enterprise_endpoint_request_mapping import (
    build_external_request_body,
    validate_request_mapping,
)
from processual_api.integrations.integration_task_catalog import get_integration_task
from processual_api.routers import settings_admin_evaluation_owned_crm_scenarios as routes
from processual_api.services.evaluation_scenarios import customer_evaluation_scenarios

WORKER = Path("deployment/evaluation-owned-sandbox/cloudflare/worker.js")


def _request() -> Request:
    path = "/settings/admin/evaluation-grants/bindings/presets/crm-summary-owned"
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "root_path": "",
        }
    )


def _admin() -> dict[str, str]:
    return {
        "sub": "evaluation-owner",
        "user_id": "evaluation-owner",
        "session_type": "identity_user",
    }


def test_summary_binding_matches_canonical_read_contract() -> None:
    body = routes.OwnedCrmSummaryPresetRequest(base_url="https://sandbox.example.com")
    binding = routes._summary_binding(body)
    validation = validate_endpoint_binding(binding)

    assert binding.task_id == "crm.customer_state_summary"
    assert binding.method == "GET"
    assert binding.path == "/users/1"
    assert binding.required_scope_ids == ["crm:read"]
    assert binding.field_mapping["account_status"] == "$.account_status"
    assert validation["operation_class"] == "read"
    assert validation["production_allowed"] is False


def test_draft_binding_and_request_mapping_are_sandbox_only_and_complete() -> None:
    body = routes.OwnedCrmDraftPresetRequest(base_url="https://sandbox.example.com")
    binding = routes._draft_binding(body)
    mapping = routes._draft_mapping(binding.binding_id)
    binding_validation = validate_endpoint_binding(binding)
    mapping_validation = validate_request_mapping(binding, mapping)
    request_body = build_external_request_body(
        binding,
        mapping,
        {
            "customer_id": "sandbox-customer-001",
            "proposed_changes": {"segment": "evaluation-review"},
        },
    )

    assert binding.task_id == "crm.customer_update_draft"
    assert binding.method == "POST"
    assert binding.path == "/users/1/update-draft"
    assert set(binding.required_scope_ids) == {"crm:read", "customer:update"}
    assert binding_validation["operation_class"] == "draft"
    assert binding_validation["production_allowed"] is False
    assert mapping_validation["production_allowed"] is False
    assert request_body == {
        "customer_id": "sandbox-customer-001",
        "proposed_changes": {"segment": "evaluation-review"},
    }


def test_guided_summary_and_draft_samples_satisfy_canonical_required_fields() -> None:
    raw = {
        BINDING_STORAGE_KEY: [
            {
                "binding_id": "evaluation.crm.customer_state_summary.owned",
                "task_id": "crm.customer_state_summary",
            },
            {
                "binding_id": "evaluation.crm.customer_update_draft.owned",
                "task_id": "crm.customer_update_draft",
            },
        ]
    }
    grant = {
        "allowed_task_ids": [
            "crm.customer_state_summary",
            "crm.customer_update_draft",
        ],
        "allowed_binding_ids": [
            "evaluation.crm.customer_state_summary.owned",
            "evaluation.crm.customer_update_draft.owned",
        ],
        "allowed_endpoints": [
            {"method": "POST", "path": "/evaluation/runtime/task-execute"}
        ],
    }

    scenarios = customer_evaluation_scenarios(raw, grant)
    by_id = {item["scenario_id"]: item for item in scenarios}

    for scenario_id, task_id in (
        ("CRM-SUMMARY-01", "crm.customer_state_summary"),
        ("CRM-DRAFT-01", "crm.customer_update_draft"),
    ):
        scenario = by_id[scenario_id]
        task = get_integration_task(task_id)
        assert scenario["runnable"] is True
        assert set(task.required_input_fields).issubset(scenario["sample_input"])
        assert scenario["production_allowed"] is False
        assert scenario["quota_cost_new_execution"] == 1
        assert scenario["quota_cost_replay"] == 0

    assert "proposed_changes" in by_id["CRM-DRAFT-01"]["sample_input"]
    assert "requested_change" not in by_id["CRM-DRAFT-01"]["sample_input"]


def test_owned_worker_draft_endpoint_is_non_mutating_by_contract() -> None:
    source = WORKER.read_text(encoding="utf-8")

    assert "Object.freeze" in source
    assert "'/users/1/update-draft'" in source
    assert "draft_only: true" in source
    assert "applied: false" in source
    assert "review_required: true" in source
    assert "production_allowed: false" in source
    assert "CUSTOMER =" in source
    assert "CUSTOMER." not in source.replace("CUSTOMER =", "")
    assert "request.method.toUpperCase()" in source
    assert "read_only_sandbox" in source


def test_owned_preset_results_never_claim_production_mutation(monkeypatch) -> None:
    async def allow(current_user, request=None):
        del request
        return current_user

    captured: list[object] = []

    async def provision(*, binding_id, body, request, current_user):
        del request, current_user
        captured.append((binding_id, body))
        return {"persisted": True}

    async def proof(*, binding_id, body, request, current_user):
        del binding_id, body, request, current_user
        return {
            "operational_proof": True,
            "peer_address_verified": True,
            "network_request_executed": True,
            "mapping_valid": True,
            "ready_for_task_consumption": True,
            "evidence_sha256": "abc123",
        }

    async def catalog_item(*, binding_id, request, current_user):
        del binding_id, request, current_user
        return {
            "selectable": True,
            "sandbox_readiness": {"status": "sandbox_ready"},
            "active_sandbox_grant": {"status": "active"},
        }

    monkeypatch.setattr(routes, "require_active_platform_admin", allow)
    monkeypatch.setattr(routes, "provision_evaluation_binding", provision)
    monkeypatch.setattr(routes, "execute_evaluation_sandbox_operational_proof", proof)
    monkeypatch.setattr(routes, "_catalog_item", catalog_item)

    summary = asyncio.run(
        routes.prepare_owned_crm_summary_preset(
            routes.OwnedCrmSummaryPresetRequest(base_url="https://sandbox.example.com"),
            _request(),
            _admin(),
        )
    )
    draft = asyncio.run(
        routes.prepare_owned_crm_update_draft_preset(
            routes.OwnedCrmDraftPresetRequest(base_url="https://sandbox.example.com"),
            _request(),
            _admin(),
        )
    )

    assert summary["production_allowed"] is False
    assert summary["production_mutation_performed"] is False
    assert draft["draft_only"] is True
    assert draft["production_allowed"] is False
    assert draft["production_mutation_performed"] is False
    assert draft["draft_contract"] == {
        "operation_class": "draft",
        "review_required": True,
        "applied": False,
        "production_mutation_performed": False,
        "production_allowed": False,
    }

    draft_provision = captured[1][1]
    assert draft_provision.request_mapping is not None
    assert draft_provision.content_contract.synthetic_or_nonproduction is True
    assert draft_provision.content_contract.raw_payloads_included is False
    assert draft_provision.secret_reference.value_included is False
