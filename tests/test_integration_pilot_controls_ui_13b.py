from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_admin_integration_pilot_controls_script_loaded_from_admin_html():
    admin_html = read("processual_api/static/admin.html")

    assert "admin_integration_pilot_controls_13b.js" in admin_html


def test_admin_integration_pilot_controls_isolated_ui_markers_exist():
    js = read("processual_api/static/js/admin_integration_pilot_controls_13b.js")

    assert "adminpilot13b-isolated-recovery" in js
    assert "PMK_ADMIN_INTEGRATION_PILOT_CONTROLS_13B" in js
    assert "/settings/admin/integration-tasks" in js
    assert "activation-permission-key" in js

    assert "data-admin-integration-activation-license-panel" in js
    assert "Integration Activation Permission License" in js
    assert "data-admin-pilot-license-generate" in js
    assert "data-admin-pilot-license-output" in js
    assert "data-admin-activation-permission-key-once" in js

    assert "data-admin-integration-pilot-tracking-panel" in js
    assert "Integration Pilot Tracking" in js
    assert "data-admin-pilot-track-table" in js
    assert "data-admin-pilot-track-create" in js
    assert "data-admin-pilot-control-action" in js

    assert "data-admin-pilot-runtime-enabled" in js
    assert "data-admin-pilot-production-allowed" in js
    assert "data-admin-pilot-external-http" in js
    assert "data-admin-pilot-secret-visible" in js

    assert "runtime=false" in js
    assert "production=false" in js
    assert "external_http=false" in js
    assert "secret_visible=false" in js

    assert "activation_permission_key_once" in js
    assert "dataset.visibleOnce" in js
    assert "iapk_****************" in js


def test_admin_api_keys_original_file_not_used_for_13b_panels():
    admin_api_keys_js = read("processual_api/static/js/admin_api_keys.js")

    assert "data-admin-integration-activation-license-panel" not in admin_api_keys_js
    assert "data-admin-integration-pilot-tracking-panel" not in admin_api_keys_js
    assert "adminpilot13b-isolated-recovery" not in admin_api_keys_js
