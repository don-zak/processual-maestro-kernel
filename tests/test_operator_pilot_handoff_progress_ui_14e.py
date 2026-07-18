"""Static UI tests for operator pilot handoff progress 14E."""

from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")

HANDOFF_JS = Path("processual_api/static/js/admin_operator_pilot_handoff.js")

HANDOFF_CSS = Path("processual_api/static/css/admin_operator_pilot_handoff.css")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_14e_progress_cache_bump_is_wired() -> None:
    html = _read(ADMIN_HTML)

    assert ("admin_operator_pilot_handoff.js?v=operatorhandoff14eprogress") in html

    assert ("admin_operator_pilot_handoff.css?v=operatorhandoff14eprogress") in html

    assert html.count("operatorhandoff14eprogress") == 2
    assert "operatorhandoff14dactions" not in html


def test_14e_progress_ui_loads_safe_backend_state() -> None:
    js = _read(HANDOFF_JS)

    required = [
        "PMK OPERATOR PILOT HANDOFF PROGRESS UI 14E START",
        "PROGRESS_API_14E",
        "/settings/admin/operator-pilot-handoff/progress",
        "normalizeProgressPackage14E",
        "progressGuardrailsAreSafe14E",
        "progress_loaded",
        "progress_rejected_guardrails",
        "progress_http_",
        "progress_error",
        'credentials: "same-origin"',
    ]

    for marker in required:
        assert marker in js


def test_14e_progress_ui_validates_all_guardrails() -> None:
    js = _read(HANDOFF_JS)

    required = [
        "guardrails.production_allowed === false",
        "guardrails.runtime_connector_approved === false",
        "guardrails.customer_credentials_present === false",
        "guardrails.external_http_allowed === false",
        "guardrails.automatic_activation_allowed === false",
        "guardrails.action_execution_allowed === false",
        "guardrails.credentials_storage_allowed === false",
        "guardrails.free_form_secret_fields_allowed === false",
        "guardrails.local_progress_tracking_only === true",
        'payload.storage !== "local_json_only"',
        "payload.actions.length !== 12",
        'action.execution_mode === "copy_only"',
    ]

    for marker in required:
        assert marker in js


def test_14e_progress_ui_uses_guarded_supervisor_headers() -> None:
    js = _read(HANDOFF_JS)

    required = [
        '"pmk_supervisor_session_key"',
        '"pmk_admin_supervisor_session"',
        '"X-Admin-Supervisor-Session"',
        '"X-Admin-Supervisor-Scope"',
        '"admin:integration_readiness:write"',
        "progressWriteAvailable14E",
        "progressHeaders14E(true)",
    ]

    for marker in required:
        assert marker in js


def test_14e_progress_ui_renders_safe_controls() -> None:
    js = _read(HANDOFF_JS)

    required = [
        "Readiness progress",
        "Safe supervisor note",
        "Save progress",
        "data-operator-pilot-progress-status",
        "data-operator-pilot-progress-note",
        "data-operator-pilot-progress-save",
        "operator-pilot-action-progress-14e",
        "pending_operator_input",
        "requested",
        "received_for_review",
        "needs_clarification",
    ]

    for marker in required:
        assert marker in js


def test_14e_progress_ui_exposes_dom_proof_datasets() -> None:
    js = _read(HANDOFF_JS)

    required = [
        "root.dataset.progressLoadState",
        "root.dataset.progressSaveState",
        "root.dataset.progressActionCount",
        "root.dataset.progressStorage",
        "root.dataset.progressTimelineEvents",
        "root.dataset.progressWriteAvailable",
        "root.dataset.progressProductionAllowed",
        "root.dataset.progressRuntimeConnectorApproved",
    ]

    for marker in required:
        assert marker in js


def test_14e_progress_ui_has_no_unsafe_execution_controls() -> None:
    js = _read(HANDOFF_JS)

    forbidden = [
        "Approve production",
        "Connect production",
        "Enable runtime connector",
        "Store credentials",
        "MutationObserver",
        "XMLHttpRequest",
        'fetch("http',
        "fetch('http",
        "safe_reference",
        "data-operator-pilot-progress-credential",
    ]

    for marker in forbidden:
        assert marker not in js


def test_14e_progress_css_is_scoped_to_handoff_page() -> None:
    css = _read(HANDOFF_CSS)

    required = [
        "PMK OPERATOR PILOT HANDOFF PROGRESS UI 14E START",
        ("#page-operator-pilot-handoff\n.operator-pilot-action-progress-14e"),
        ("#page-operator-pilot-handoff\n.operator-pilot-progress-field"),
        ("#page-operator-pilot-handoff\n.operator-pilot-progress-save"),
        ("#page-operator-pilot-handoff\n.operator-pilot-progress-message"),
        'data-state="success"',
        'data-state="error"',
    ]

    for marker in required:
        assert marker in css
