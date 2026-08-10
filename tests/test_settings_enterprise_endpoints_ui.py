from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js" / "settings_enterprise_endpoints.js"
CSS = ROOT / "processual_api" / "static" / "css" / "settings_enterprise_endpoints.css"
APP = ROOT / "processual_api" / "static" / "js" / "app.js"


def test_endpoint_binding_ui_assets_are_bootstrapped() -> None:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "settings_enterprise_endpoints.js" in app
    assert "settings_enterprise_endpoints.css" in app
    assert "PMK_SETTINGS_ENTERPRISE_ENDPOINTS" in app
    assert "PMK_SETTINGS_ENTERPRISE_ENDPOINTS" in js
    assert ".see-workspace" in css


def test_ui_uses_server_authoritative_task_and_binding_catalogs() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "/settings/enterprise-integration/task-catalog" in js
    assert "/settings/enterprise-integration/endpoint-bindings" in js
    assert "/settings/enterprise-integration" in js
    assert "taskCatalog.map" in js
    assert "adapter_contract_id" in js
    assert "required_scope_ids: task.required_scope_ids" in js


def test_ui_covers_mapping_and_canonical_preview_without_raw_secret_fields() -> None:
    js = JS.read_text(encoding="utf-8")
    lowered = js.lower()
    assert "field_mapping" in js
    assert "response_data_path" in js
    assert "mapping-preview" in js
    assert "canonical_input" in js
    assert "credential_profile_id" in js
    assert "credential_material_included" not in js
    assert 'name="authorization"' not in lowered
    assert "raw_secret" not in lowered
    assert "password" not in lowered


def test_ui_explicitly_preserves_sandbox_and_production_boundary() -> None:
    js = JS.read_text(encoding="utf-8")
    assert "environment: 'sandbox'" in js
    assert "Sandbox configuration" in js
    assert "Production blocked" in js
    assert "No network request or production activation was performed." in js


def test_ui_has_accessible_live_status_focus_and_responsive_layout() -> None:
    js = JS.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert "aria-live" in js
    assert "aria-labelledby" in js
    assert ":focus-visible" in css
    assert "@media(max-width:820px)" in css
    assert "prefers-reduced-motion" in css
    assert "border-inline-start" in css
