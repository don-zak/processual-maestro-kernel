from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
HANDOFF_JS = Path("processual_api/static/js/admin_operator_pilot_handoff.js")
HANDOFF_CSS = Path("processual_api/static/css/admin_operator_pilot_handoff.css")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_operator_pilot_handoff_14d_cache_bump_is_wired() -> None:
    html = _read(ADMIN_HTML)

    assert "admin_operator_pilot_handoff.js?v=operatorhandoff14eprogress" in html
    assert "admin_operator_pilot_handoff.css?v=operatorhandoff14eprogress" in html
    assert "operatorhandoff14cbackend" not in html


def test_operator_pilot_handoff_14d_loads_safe_actions_preview() -> None:
    js = _read(HANDOFF_JS)

    expected = [
        "PMK OPERATOR PILOT HANDOFF ACTIONS UI 14D START",
        "OPERATOR_PILOT_HANDOFF_ACTIONS_API_14D",
        "/settings/admin/operator-pilot-handoff/actions-preview",
        "async function loadActionsPackage14D",
        "normalizeActionsPackage14D",
        'credentials: "same-origin"',
        "actions_loaded",
        "actions_http_",
        "actions_rejected_guardrails",
        "actions_error",
    ]

    for marker in expected:
        assert marker in js


def test_operator_pilot_handoff_14d_rejects_unsafe_actions() -> None:
    js = _read(HANDOFF_JS)

    expected = [
        "payload.read_only !== true",
        "payload.preview_only !== true",
        "guardrails.production_allowed !== false",
        "guardrails.runtime_connector_approved !== false",
        "guardrails.customer_credentials_present !== false",
        "guardrails.external_http_allowed !== false",
        "guardrails.persistent_write_allowed !== false",
        "guardrails.automatic_activation_allowed !== false",
        'action.execution_mode === "copy_only"',
        "action.requires_credentials === false",
        "action.requires_production === false",
        "action.persistent_write_allowed === false",
    ]

    for marker in expected:
        assert marker in js


def test_operator_pilot_handoff_14d_renders_copy_only_controls() -> None:
    js = _read(HANDOFF_JS)

    assert "Supervisor readiness actions" in js
    assert 'panel.id = "operator-pilot-actions-14d"' in js
    assert "operator-pilot-actions-grid" in js
    assert "operator-pilot-action-card" in js
    assert "data-operator-pilot-copy-action" in js
    assert "Copy request note" in js
    assert "root.dataset.actionsLoadState" in js
    assert "root.dataset.actionsCount" in js
    assert "root.dataset.actionsReadOnly" in js
    assert "root.dataset.actionsPreviewOnly" in js


def test_operator_pilot_handoff_14d_has_no_unsafe_execution_ui() -> None:
    js = _read(HANDOFF_JS)

    forbidden = [
        "Approve production",
        "Connect production",
        "Store credentials",
        "Enable runtime connector",
        "XMLHttpRequest",
        "MutationObserver",
        'fetch("http',
        "fetch('http",
    ]

    for marker in forbidden:
        assert marker not in js


def test_operator_pilot_handoff_14d_css_is_page_scoped() -> None:
    css = _read(HANDOFF_CSS)

    assert "PMK OPERATOR PILOT HANDOFF ACTIONS UI 14D START" in css
    assert "#page-operator-pilot-handoff .operator-pilot-actions-14d" in css
    assert "#page-operator-pilot-handoff .operator-pilot-actions-grid" in css
    assert "#page-operator-pilot-handoff .operator-pilot-action-card" in css
    assert "#page-operator-pilot-handoff .operator-pilot-action-copy" in css
    assert "grid-template-columns: repeat(auto-fit, minmax(260px, 1fr))" in css
