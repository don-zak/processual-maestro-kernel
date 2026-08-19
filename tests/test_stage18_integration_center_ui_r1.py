# ruff: noqa

import re
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
    assert "/settings/admin/integration-center/camara-qod-qualification" in center
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


def test_stage18_workspace_styles_are_loaded_and_responsive():
    app = _text("processual_api/static/js/app.js")
    nav = _text("processual_api/static/js/admin_nav.js")
    institution_css = _text(
        "processual_api/static/css/institution_workspace_18.css"
    )
    integration_center_css = _text(
        "processual_api/static/css/admin_integration_center_18.css"
    )

    assert "css/institution_workspace_18.css" in app
    assert "/console/css/admin_integration_center_18.css" in nav
    assert ".iw18-track-grid" in institution_css
    assert ".iw18-task-grid" in institution_css
    assert "@media(max-width:620px)" in institution_css
    assert ".ic18-metrics" in integration_center_css
    assert ".ic18-rail" in integration_center_css
    assert ".ic18-platform-grid" in integration_center_css
    assert ".ic18-readiness-step" in integration_center_css
    assert "@media(max-width:640px)" in integration_center_css
    assert "@media(prefers-reduced-motion:reduce)" in integration_center_css


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


def test_integration_center_platforms_distinguish_contract_from_live_proof():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "Platform qualification, not logo compatibility" in center
    assert "Architecture family" in center
    assert "Reviewed release candidate" in center
    assert "Server-enabled trusted source" in center
    assert "Live source acquisition" in center
    assert "Semantic task mapping" in center
    assert "Governance contract review" in center
    assert "Live operator sandbox" in center
    assert "Production approval" in center
    assert "Provider API version" in center
    assert "Live provider proof" in center
    assert "Blocked" in center


def test_integration_center_camara_status_is_route_backed_and_fail_closed():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert 'camaraQod: "/settings/admin/integration-center/camara-qod-qualification"' in center
    assert "camaraQod: null" in center
    assert "getJson(API.camaraQod)" in center
    assert 'state.camaraQod = results[4].status === "fulfilled" ? results[4].value : null' in center
    assert 'payload.status === "reviewed_qualification_contract"' in center
    assert "payload.server_trusted_source_enabled === true" in center
    assert 'payload.semantic_mapping_state === "proposal_only"' in center
    assert "callableOperations.length === 5" in center
    assert 'payload.governance_candidate_state === "review_required"' in center
    assert "payload.governance_candidate_valid === true" in center
    assert "payload.governance_approved === false" in center
    assert "governanceTasks.length === 5" in center
    assert "governanceEntitlements.length === 2" in center
    assert "governanceQuotas.length === 5" in center
    assert "payload.live_source_acquisition_proven === true" in center
    assert "payload.provider_sandbox_proven === true" in center
    assert "Qualification status route unavailable. Conservative fallback" in center
    assert "governance approval, provider sandbox and runtime authority unproven" in center


def test_integration_center_camara_candidate_is_pinned_without_overclaiming():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "Quality on Demand · r3.2 candidate" in center
    assert "QoD v${version}" in center
    assert "9cb179f" in center
    assert "code/API_definitions/quality-on-demand.yaml" in center
    assert "Spec candidate pinned" in center
    assert 'const sourceStatus = sourceEnabled ? "Policy enabled" : "Pending"' in center
    assert 'const semanticStatus = semanticReviewed ? "Reviewed proposal" : "Pending"' in center
    assert 'const governanceStatus = governanceReadyForReview ? "Review required" : "Pending"' in center
    assert 'const liveStatus = liveProven ? "Proven" : "Not proven"' in center
    assert 'const sandboxStatus = providerSandboxProven ? "Proven" : "Blocked"' in center
    assert "explicit governance approval is still required before runtime registration" in center
    assert "runtime task registration remains disabled" in center
    assert "CAMARAConnectorQualified=True" not in center
    assert "Production allowed" not in center


def test_integration_center_qod_governance_state_is_reviewable_not_authoritative():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "governanceReadyForReview" in center
    assert "Review required" in center
    assert "task candidates" in center
    assert "entitlement candidates" in center
    assert "quota meters" in center
    assert "still require explicit governance approval" in center
    assert "governanceReadyForReview ? \"is complete for review\" : \"is incomplete\"" in center
    assert "governance approval" in center


def test_integration_center_qod_mapping_priority_reflects_governance_not_missing_mapping():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "Review/register QoD task contracts" in center
    assert "pending governance" in center
    assert "five-operation semantic proposal, task candidates, entitlement candidates and quota meters are internally consistent" in center
    assert "Map CAMARA QoD operations" not in center


def test_integration_center_status_semantics_do_not_treat_not_proven_as_warning():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "not proven" in center
    assert "/reject|block|fail|expired|no-go|not qualified|disabled|not proven/" in center
    assert "Ready / pinned" in center
    assert "Blocked / not proven" in center


def test_integration_center_exposes_real_transport_guardrails():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "HTTPS-only destinations" in center
    assert "Public-address DNS verification" in center
    assert "Redirect following" in center
    assert "Path-segment composition" in center
    assert "percent-encoded as one route segment" in center
    assert "JSON-only parsing with a 1 MiB response ceiling" in center


def test_integration_center_has_accessible_navigation_and_status_semantics():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert 'role="tablist"' in center
    assert 'role="tab"' in center
    assert 'role="tabpanel"' in center
    assert 'aria-controls="ic18-panel-${key}"' in center
    assert 'aria-labelledby="ic18-tab-${state.active}"' in center
    assert 'aria-selected="${state.active === key ? "true" : "false"}"' in center
    assert 'tabindex="${state.active === key ? "0" : "-1"}"' in center
    assert 'role="status"' in center
    assert 'role="alert"' in center
    assert 'aria-label="Environment authority"' in center
    assert 'aria-label="Integration readiness metrics"' in center
    assert 'aria-label="Readiness legend"' in center
    assert 'type="button"' in center
    assert "Loading integration readiness, cases, CAMARA qualification and pilot evidence" in center


def test_integration_center_tabs_support_standard_keyboard_navigation():
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert 'event.key === "ArrowRight"' in center
    assert 'event.key === "ArrowLeft"' in center
    assert 'event.key === "Home"' in center
    assert 'event.key === "End"' in center
    assert "event.preventDefault()" in center
    assert "window.requestAnimationFrame" in center
    assert "activeTab.focus()" in center


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
        "private_key=",
        "password=",
    )
    for marker in forbidden:
        assert marker not in combined

    assert re.search(r"(?<![a-z0-9_-])sk-[a-z0-9_-]{16,}", combined) is None
