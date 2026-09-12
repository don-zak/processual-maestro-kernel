from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.routers import settings_admin_evaluation_grants as grant_routes

ROOT = Path(__file__).resolve().parents[1]
ADMIN_GUARD = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_binding_coverage_guard.js"
ADMIN_BUNDLE = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_crm_bundle.js"
ADMIN_DOM = ROOT / "processual_api" / "static" / "js" / "admin_external_evaluation_dom_contract.js"


def _runtime_endpoint() -> list[dict[str, str]]:
    return [{"method": "POST", "path": "/evaluation/runtime/task-execute"}]


def _raw_bindings() -> dict:
    return {
        BINDING_STORAGE_KEY: [
            {"binding_id": "binding-context", "task_id": "crm.customer_context"},
            {"binding_id": "binding-summary", "task_id": "crm.customer_state_summary"},
            {"binding_id": "binding-draft", "task_id": "crm.customer_update_draft"},
        ]
    }


def _patch_binding_validation(monkeypatch) -> None:
    monkeypatch.setattr(
        grant_routes,
        "EnterpriseEndpointBindingSpec",
        lambda **item: SimpleNamespace(**item),
    )
    monkeypatch.setattr(grant_routes, "validate_endpoint_binding", lambda _spec: None)


def test_backend_rejects_selected_tasks_without_complete_binding_coverage(monkeypatch) -> None:
    _patch_binding_validation(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        grant_routes._binding_selection(
            _raw_bindings(),
            ["binding-context", "binding-summary"],
            task_ids=[
                "crm.customer_context",
                "crm.customer_state_summary",
                "crm.customer_update_draft",
            ],
            endpoints=_runtime_endpoint(),
        )

    assert exc.value.status_code == 422
    assert "Every runtime evaluation task requires a selected prepared binding" in str(exc.value.detail)
    assert "crm.customer_update_draft" in str(exc.value.detail)


def test_backend_accepts_exact_complete_task_binding_coverage(monkeypatch) -> None:
    _patch_binding_validation(monkeypatch)

    selected = grant_routes._binding_selection(
        _raw_bindings(),
        ["binding-context", "binding-summary", "binding-draft"],
        task_ids=[
            "crm.customer_context",
            "crm.customer_state_summary",
            "crm.customer_update_draft",
        ],
        endpoints=_runtime_endpoint(),
    )

    assert selected == ["binding-context", "binding-summary", "binding-draft"]


def test_admin_guard_fails_closed_until_every_selected_task_has_a_binding() -> None:
    guard = ADMIN_GUARD.read_text(encoding="utf-8")
    dom = ADMIN_DOM.read_text(encoding="utf-8")

    for marker in (
        "missing prepared binding coverage",
        "Runtime grant remains LOCKED",
        "button.disabled = true",
        "bindingCoverageReady",
        "selectedTasks()",
        "selectedBindings()",
        "bindingTaskById",
    ):
        assert marker in guard

    assert "admin_evaluation_binding_coverage_guard.js?v=eval-binding-coverage-v1" in dom
    assert "ensureBindingCoverageGuardScript" in dom


def test_admin_complete_crm_bundle_runs_all_three_presets_before_grant_creation() -> None:
    bundle = ADMIN_BUNDLE.read_text(encoding="utf-8")
    dom = ADMIN_DOM.read_text(encoding="utf-8")

    for marker in (
        "CRM-CONTEXT-01",
        "CRM-SUMMARY-01",
        "CRM-DRAFT-01",
        "Prepare complete CRM bundle",
        "CRM BUNDLE READY",
        "Grant creation remains locked until all three live proofs succeed",
        "refreshBindingCatalog",
        "PMK_ADMIN_EVALUATION_BINDING_COVERAGE_GUARD",
    ):
        assert marker in bundle

    assert "admin_evaluation_crm_bundle.js?v=eval-crm-bundle-v1" in dom
    assert "ensureCrmBundleScript" in dom
