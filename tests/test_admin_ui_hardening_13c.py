from pathlib import Path


def test_admin_ui_hardening_13c_assets_are_loaded():
    html = Path("processual_api/static/admin.html").read_text(encoding="utf-8")
    assert "/console/css/admin_ui_hardening_13c.css?v=adminui13c" in html
    assert "/console/js/admin_ui_hardening_13c.js?v=adminui13c" in html
    assert "/console/js/admin_integration_pilot_controls_13b.js" in html
    assert "/static/js/admin_integration_pilot_controls_13b.js" not in html
    assert "â€¦" not in html


def test_admin_ui_hardening_13c_css_table_and_card_contract():
    css = Path("processual_api/static/css/admin_ui_hardening_13c.css").read_text(encoding="utf-8")
    assert "ADMIN_UI_HARDENING_13C" in css
    assert ".pmk-admin-card" in css
    assert ".pmk-admin-table-frame" in css
    assert "overflow-x: auto" in css
    assert ".pmk-admin-actions-cell" in css
    assert ".pmk-admin-boolean-chip" in css
    assert "raw_secret" not in css.lower()


def test_admin_ui_hardening_13c_js_is_presentation_only():
    js = Path("processual_api/static/js/admin_ui_hardening_13c.js").read_text(encoding="utf-8")
    assert "ADMIN_UI_HARDENING_13C" in js
    assert "PMK_ADMIN_UI_HARDENING_13C" in js
    assert "wrapTables" in js
    assert "groupActionButtons" in js
    assert "chipBareBooleans" in js
    assert "collapseLargeJsonBlocks" in js
    assert "fetch(" not in js
    assert "XMLHttpRequest" not in js
    assert "raw_key" not in js.lower()
    assert "raw_secret" not in js.lower()
    assert "production_allowed = true" not in js
    assert "runtime_connector_approved = true" not in js

def test_admin_ui_hardening_13c_r2_guardrail_labels_and_button_contrast():
    js = Path("processual_api/static/js/admin_ui_hardening_13c.js").read_text(encoding="utf-8")
    css = Path("processual_api/static/css/admin_ui_hardening_13c.css").read_text(encoding="utf-8")
    assert "admin-ui-hardening-13c-r2" in js
    assert "labelGuardrailBooleans" in js
    assert "Runtime enabled" in js
    assert "Production allowed" in js
    assert "External HTTP" in js
    assert "Raw secret visible" in js
    assert "13C-R2: explicit button contrast" in css
    assert "color: #f8fbff !important" in css
    assert ".pmk-admin-guardrail-caption" in css
    assert "data-guardrail-label" in css
