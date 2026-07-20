# ruff: noqa

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_stage18_admin_integration_center_is_wired_to_existing_safe_routes():
    nav = _text("processual_api/static/js/admin_nav.js")
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "integration-center" in nav
    assert "admin-integration-center-root" in nav
    assert "/settings/admin/integration-readiness-tracking/cases" in center
    assert "/settings/admin/operator-pilot-handoff" in center
    assert "/settings/admin/operator-pilot-handoff/progress" in center
    assert "Production" in center
    assert "NO-GO" in center
    assert "No raw secrets" in center


def test_enterprise_workspace_is_bootstrapped_without_internal_stage_labels():
    app = _text("processual_api/static/js/app.js")
    workspace = _text("processual_api/static/js/pages/institution_workspace_18.js")

    assert 'data-page="institution"' in app
    assert "Enterprise Workspace" in app
    assert ">Enterprise<" in app
    assert "institution-workspace-root" in app
    assert "Enterprise workspace" in workspace
    assert "Stage 18 R3" not in workspace
    assert "Production blocked" in workspace


def test_enterprise_workspace_exposes_operational_tracks_and_tasks():
    workspace = _text("processual_api/static/js/pages/institution_workspace_18.js")

    assert "CAMARA / GSMA Open Gateway" in workspace
    assert "TM Forum Open APIs" in workspace
    assert "Operator-specific integration" in workspace
    assert "Create operational case" in workspace
    assert "Save task" in workspace
    assert "Run automated validation" in workspace
    assert "progress_percent" in workspace
    assert "ready_for_review" in workspace


def test_enterprise_workspace_uses_formal_case_routes_not_support_messages():
    workspace = _text("processual_api/static/js/pages/institution_workspace_18.js")

    assert "createTrackCase" in workspace
    assert "CLIENT.post('/settings/client/integration-cases'" in workspace
    assert "/settings/client/integration-cases/${encodeURIComponent(caseId)}/tasks/" in workspace
    assert "/settings/client/integration-cases/${encodeURIComponent(caseId)}/validate" in workspace
    assert "CLIENT.patch" in workspace
    assert "CLIENT.post('/settings/client-request'" not in workspace
    assert "requested_phase=supervisor_review" not in workspace


def test_enterprise_workspace_limits_supervisor_to_decision_gate():
    workspace = _text("processual_api/static/js/pages/institution_workspace_18.js")

    assert "Supervisor involvement begins only after automated validation passes." in workspace
    assert "Self-service" in workspace
    assert "Supervisor decision" in workspace
    assert "production_allowed=false" in workspace
    assert "runtime_connector_approved=false" in workspace
    assert "raw_secret_visible=false" in workspace


def test_stage18_new_ui_does_not_embed_secret_material():
    combined = "\n".join(
        [
            _text("processual_api/static/js/admin_integration_center_18.js"),
            _text("processual_api/static/js/pages/institution_workspace_18.js"),
        ]
    ).lower()

    forbidden = (
        "client_secret=",
        "access_token=",
        "authorization: bearer ",
        "sk-",
        "private_key=",
        "password=",
    )
    for marker in forbidden:
        assert marker not in combined
