from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"
ADMIN_NAV_JS = ROOT / "processual_api" / "static" / "js" / "admin_nav.js"
HANDOFF_JS = ROOT / "processual_api" / "static" / "js" / "admin_operator_pilot_handoff.js"
HANDOFF_CSS = (
    ROOT / "processual_api" / "static" / "css" / "admin_operator_pilot_handoff.css"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _handoff_section_chunk() -> str:
    html = _read(ADMIN_HTML)
    section_start = html.find('id="page-operator-pilot-handoff"')
    assert section_start >= 0
    return html[section_start : section_start + 640]


def test_operator_pilot_handoff_14a_admin_page_is_wired() -> None:
    html = _read(ADMIN_HTML)
    section_chunk = _handoff_section_chunk()

    assert 'id="page-operator-pilot-handoff"' in html
    assert 'id="operator-pilot-handoff-root"' in html
    assert 'data-admin-page="operator-pilot-handoff"' in html
    assert "Pilot Handoff" in html
    assert "admin_operator_pilot_handoff.js?v=operatorhandoff14cbackend" in html
    assert "admin_operator_pilot_handoff.css?v=operatorhandoff14cbackend" in html

    assert 'class="admin-page admin-operator-pilot-handoff-page"' in section_chunk


def test_operator_pilot_handoff_14a_is_registered_in_admin_nav_switchers() -> None:
    html = _read(ADMIN_HTML)
    admin_nav_js = _read(ADMIN_NAV_JS)

    expected_mapping = "'operator-pilot-handoff': 'page-operator-pilot-handoff'"

    assert expected_mapping in html
    assert expected_mapping in admin_nav_js


def test_operator_pilot_handoff_has_no_runtime_visibility_guard() -> None:
    js = _read(HANDOFF_JS)
    css = _read(HANDOFF_CSS)

    forbidden_runtime_guard_markers = [
        "MutationObserver",
        "startStandaloneVisibilityGuard",
        "ensureStandaloneVisibility",
        "visibleStandalone",
        "visibilityGuardStarted",
    ]

    for marker in forbidden_runtime_guard_markers:
        assert marker not in js

    assert "display: block !important" not in css
    assert "visibility: visible !important" not in css


def test_operator_pilot_handoff_supervisor_tools_are_visible_and_safe() -> None:
    js = _read(HANDOFF_JS)

    expected_markers = [
        "operator-pilot-handoff-14a",
        "operator-pilot-rebuild",
        "operator-pilot-copy-checklist",
        "operator-pilot-copy-markdown",
        "operator-pilot-export",
        "pending_operator_inputs",
        "production_allowed: false",
        "runtime_connector_approved: false",
        "customer_credentials_present: false",
        "external_http_allowed: false",
    ]

    for marker in expected_markers:
        assert marker in js

    forbidden_markers = [
        "Approve production",
        "Connect production",
        "Store credentials",
        "runtime_connector_approved: true",
        "production_allowed: true",
        "XMLHttpRequest",
        "MutationObserver",
        'fetch("http',
        "fetch('http",
    ]

    for marker in forbidden_markers:
        assert marker not in js


def test_operator_pilot_handoff_expanded_domains_are_rendered() -> None:
    js = _read(HANDOFF_JS)

    expected_markers = [
        "Telecom operators",
        "Banks and fintech",
        "Government and public services",
        "Universities and research",
        "Healthcare administration",
        "Insurance providers",
        "Utilities and energy",
        "Logistics and transport",
        "Enterprise helpdesk",
        "Legal and compliance",
    ]

    for marker in expected_markers:
        assert marker in js


def test_operator_pilot_handoff_css_is_scoped_to_official_page() -> None:
    css = _read(HANDOFF_CSS)

    assert "#page-operator-pilot-handoff" in css
    assert ".operator-pilot-shell" in css
    assert ".operator-pilot-tools" in css
    assert ".operator-pilot-specializations" in css
    assert ".operator-pilot-guardrails" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))" in css


def test_operator_pilot_handoff_ui_explains_supervisor_handoff_scope() -> None:
    js = _read(HANDOFF_JS)
    css = _read(HANDOFF_CSS)

    assert "function ensureExplanationPanel" in js
    assert "operator-pilot-explainer" in js
    assert "What this handoff page does" in js
    assert "What remains blocked" in js
    assert "Next operator action" in js

    assert ".operator-pilot-explainer-grid" in css
    assert ".operator-pilot-explainer-card" in css
    assert ".operator-pilot-tools button" in css
    assert "color: var(--text)" in css

    assert "MutationObserver" not in js
    assert "XMLHttpRequest" not in js
    assert 'fetch("http' not in js
    assert "fetch('http" not in js


def test_operator_pilot_handoff_14c_loads_from_backend_with_safe_fallback() -> None:
    html = _read(ADMIN_HTML)
    js = _read(HANDOFF_JS)

    assert "admin_operator_pilot_handoff.js?v=operatorhandoff14cbackend" in html
    assert "admin_operator_pilot_handoff.css?v=operatorhandoff14cbackend" in html

    assert 'OPERATOR_PILOT_HANDOFF_API_14C = "/settings/admin/operator-pilot-handoff"' in js
    assert "OPERATOR_PILOT_HANDOFF_EXPORT_API_14C" in js
    assert "async function loadBackendPackage14C" in js
    assert "normalizeBackendPackage14C" in js
    assert "backendLoadState14C" in js
    assert "backend_loaded" in js
    assert "backend_rejected_guardrails" in js
    assert "static_fallback" in js
    assert "await loadBackendPackage14C()" in js

    assert "fetch(OPERATOR_PILOT_HANDOFF_API_14C" in js
    assert 'credentials: "same-origin"' in js
    assert "window.open(OPERATOR_PILOT_HANDOFF_EXPORT_API_14C" in js

    assert "XMLHttpRequest" not in js
    assert "MutationObserver" not in js
    assert 'fetch("http' not in js
    assert "fetch('http" not in js


def test_operator_pilot_handoff_14c_rejects_unsafe_backend_guardrails() -> None:
    js = _read(HANDOFF_JS)

    guardrail_markers = [
        "guardrails.production_allowed !== false",
        "guardrails.runtime_connector_approved !== false",
        "guardrails.customer_credentials_present !== false",
        "guardrails.external_http_allowed !== false",
    ]

    for marker in guardrail_markers:
        assert marker in js

def test_operator_pilot_handoff_14c_exposes_backend_load_state_for_browser_proof() -> None:
    js = _read(HANDOFF_JS)

    assert "root.dataset.backendLoadState = backendLoadState14C" in js
    assert "const guardrails = PACKAGE.guardrails || PACKAGE" in js
    assert "root.dataset.productionAllowed = String(guardrails.production_allowed)" in js
    assert "guardrails.runtime_connector_approved" in js
    assert "backend_loaded" in js
    assert "backend_error" in js
    assert "backend_http_" in js
    assert "backend_rejected_guardrails" in js
