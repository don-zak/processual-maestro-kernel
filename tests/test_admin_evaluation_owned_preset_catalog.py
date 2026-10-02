from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_owned_preset.js"


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_all_owned_evaluation_scenarios_are_exposed_through_backend_proof_routes() -> None:
    source = _source()

    expected = {
        "CRM-CONTEXT-01": "/settings/admin/evaluation-grants/bindings/presets/crm-context-owned",
        "CRM-SUMMARY-01": "/settings/admin/evaluation-grants/bindings/presets/crm-summary-owned",
        "CRM-DRAFT-01": "/settings/admin/evaluation-grants/bindings/presets/crm-update-draft-owned",
        "INT-BILLING-01": "/settings/admin/evaluation-grants/bindings/presets/integration-billing-owned",
    }
    for scenario_id, endpoint in expected.items():
        assert scenario_id in source
        assert endpoint in source


def test_ui_requires_complete_live_proof_before_marking_scenario_ready() -> None:
    source = _source()

    for marker in (
        "payload.binding_selectable === true",
        "proof.operational_proof === true",
        "proof.peer_address_verified === true",
        "proof.network_request_executed === true",
        "proof.mapping_valid === true",
        "proof.ready_for_task_consumption === true",
        "payload.production_allowed === false",
    ):
        assert marker in source

    assert "remains BLOCKED" in source
    assert "UI presence alone grants no authority" in source


def test_crm_draft_remains_non_applying_and_nonproduction() -> None:
    source = _source()

    assert "preset.id === 'CRM-DRAFT-01'" in source
    assert "draft.applied !== false" in source
    assert "draft.production_mutation_performed !== false" in source
    assert "draft.production_allowed !== false" in source


def test_evaluation_quota_guidance_matches_grant_types() -> None:
    source = _source()

    assert "evaluationType: 'crm'" in source
    assert "quota: 100" in source
    assert "evaluationType: 'integration'" in source
    assert "quota: 200" in source
