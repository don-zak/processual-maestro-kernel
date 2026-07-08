from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
ADMIN_JS = Path("processual_api/static/js/admin_integration_readiness.js")


def test_admin_integration_readiness_script_is_loaded() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8")
    assert "admin_integration_readiness.js" in html
    assert "adminintegrationreadiness11k" in html


def test_admin_integration_readiness_card_markers_exist() -> None:
    js = ADMIN_JS.read_text(encoding="utf-8")
    markers = (
        "admin-integration-readiness-card",
        "Admin integration readiness",
        "Integration Readiness",
        "/settings/admin/integration-readiness",
        "admin-integration-readiness-total",
        "admin-integration-readiness-blocked",
        "admin-integration-readiness-sandbox-ready",
        "admin-integration-readiness-production",
        "admin-integration-readiness-runtime",
        "PMK_ADMIN_INTEGRATION_READINESS",
    )
    for marker in markers:
        assert marker in js


def test_admin_integration_readiness_ui_preserves_guardrails() -> None:
    js = ADMIN_JS.read_text(encoding="utf-8")
    assert "No raw secrets" in js
    assert "no external HTTP" in js
    assert "no runtime connector approval" in js
    assert "production_allowed=" in js
    assert "runtime_connector_approved=" in js
    assert "Production and runtime connector approvals remain false" in js
    assert "fetch(" + chr(34) + "http" not in js
    assert "production_connector_approved: true" not in js
    assert "runtime_connector_approved: true" not in js
