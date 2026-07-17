from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_HTML = ROOT / "processual_api/static/admin.html"
DASHBOARD_JS = ROOT / "processual_api/static/js/admin_operator_pilot_handoff_17c.js"
DASHBOARD_CSS = ROOT / "processual_api/static/css/admin_operator_pilot_handoff_17c.css"
LEGACY_JS = ROOT / "processual_api/static/js/admin_operator_pilot_handoff.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_17c_assets_are_wired_after_legacy_compatibility_assets() -> None:
    html = _read(ADMIN_HTML)

    legacy = html.index("admin_operator_pilot_handoff.js?v=operatorhandoff14eprogress")
    dashboard = html.index("admin_operator_pilot_handoff_17c.js?v=pilothandoff17cr1")

    assert legacy < dashboard
    assert "admin_operator_pilot_handoff_17c.css?v=pilothandoff17cr1" in html
    assert "PMK_OPERATOR_PILOT_HANDOFF_17C_ENABLED" in _read(LEGACY_JS)


def test_17c_dashboard_has_case_header_phase_rail_and_six_tabs() -> None:
    js = _read(DASHBOARD_JS)

    for marker in (
        "Integration Pilot Workspace",
        "Pilot ID",
        "Organization",
        "Environment",
        "Owner",
        "Last updated",
        "Inputs",
        "Sandbox validation",
        "Production review",
        "Overview",
        "Intake & Validation",
        "Required Inputs",
        "Reviews & Controls",
        "Pilot Plan",
        "Evidence & Audit",
    ):
        assert marker in js


def test_17c_intake_explains_and_implements_reference_data_flow() -> None:
    js = _read(DASHBOARD_JS)

    for marker in (
        "Prepare",
        "Import",
        "Validate",
        "Review",
        "Safe JSON manifest",
        "Paste manifest",
        "Automated intake",
        "pilot-handoff-intake-17c-r1",
        "/settings/admin/operator-pilot-handoff/intake-preview",
        "Validate package",
        "No persistence in R1.",
        "Secret-bearing fields are prohibited",
        "Maximum 256 KB",
    ):
        assert marker in js


def test_17c_uses_tables_instead_of_repeated_action_cards() -> None:
    js = _read(DASHBOARD_JS)

    assert "<table>" in js
    assert "Required inputs" in js
    assert "Reviews &amp; controls" in js
    assert "Pilot plan" in js
    assert "operator-pilot-action-card" not in js
    assert "Supported organization types and domains" not in js
    assert "What this handoff page does" not in js


def test_17c_handles_loading_unauthorized_error_and_empty_states() -> None:
    js = _read(DASHBOARD_JS)

    for marker in (
        'loadState: "loading"',
        '"unauthorized"',
        '"backend_unavailable"',
        "Admin session expired",
        "Sign in again",
        "Pilot data could not be loaded",
        "No case-specific input actions are available.",
        "No case evidence has been attached.",
    ):
        assert marker in js


def test_17c_ui_remains_default_deny_and_has_no_operational_control() -> None:
    js = _read(DASHBOARD_JS)

    assert 'host.dataset.productionAllowed = "false"' in js
    assert 'host.dataset.runtimeConnectorApproved = "false"' in js
    assert "This is not sandbox authorization." in js

    for forbidden in (
        "production_allowed: true",
        "runtime_connector_approved: true",
        "XMLHttpRequest",
        "MutationObserver",
        'fetch("http',
        "Store credential values",
    ):
        assert forbidden not in js


def test_17c_css_is_scoped_responsive_and_accessible() -> None:
    css = _read(DASHBOARD_CSS)

    assert css.count("#page-operator-pilot-handoff") >= 40
    assert ".pmk17c-phase-rail" in css
    assert ".pmk17c-tabs" in css
    assert ".pmk17c-table-wrap" in css
    assert ".pmk17c-dropzone" in css
    assert "@media (max-width: 820px)" in css
    assert "@media (max-width: 580px)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ":focus-visible" in css
    assert "overflow-x: auto" in css
    assert "#page-operator-pilot-handoff.active" in css
    assert "overflow-y: auto" in css
    assert "container-type: inline-size" in css
    assert "@container pmk17c-workspace (max-width: 820px)" in css
    assert "@media (max-height: 520px) and (orientation: landscape)" in css
    assert "overflow-wrap: anywhere" in css


def test_17c_shell_exposes_stable_visual_diagnostic_state() -> None:
    js = _read(DASHBOARD_JS)

    for marker in (
        'data-phase="pilot-handoff-17c-r1"',
        'data-load-state=',
        'data-active-tab=',
        'data-production-allowed="false"',
        'data-runtime-connector-approved="false"',
        "formatTimestamp",
        'timeZone: "UTC"',
    ):
        assert marker in js
