
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_client_request_detail_renders_integration_key_bridge() -> None:
    js = _read("processual_api/static/js/admin_client_requests.js")

    assert "ADMIN-INTEGRATION-KEYS-11F bridge begin" in js
    assert "admin-client-request-integration-key-bridge" in js
    assert "admin-client-request-open-integration-keys" in js
    assert "renderAdminIntegrationKeyBridgePanel(detail, body)" in js
    assert "pmk-admin-integration-key-bridge" in js
    assert "pmk_admin_integration_key_bridge" in js


def test_admin_integration_key_bridge_uses_safe_service_profile() -> None:
    js = _read("processual_api/static/js/admin_client_requests.js")

    assert "service_integration" in js
    assert "production_connector_approved: false" in js
    assert "raw_secret_visible: false" in js
    assert "does not reveal raw secrets" in js
    assert "does not approve a production connector" in js


def test_admin_api_key_panel_accepts_pending_bridge_context() -> None:
    js = _read("processual_api/static/js/admin_api_keys.js")

    assert "ADMIN-INTEGRATION-KEYS-11F pending bridge begin" in js
    assert "PMK_ADMIN_INTEGRATION_KEY_BRIDGE" in js
    assert "pmk-admin-integration-key-bridge" in js
    assert "admin-api-key-client-id" in js
    assert "admin-api-key-user-id" in js
    assert "admin-api-key-purpose" in js
    assert "service_integration" in js
    assert "No raw secrets are shown" in js


def test_admin_html_cache_bumps_bridge_scripts() -> None:
    html = _read("processual_api/static/admin.html")

    assert "admin_api_keys.js?v=adminsuperkeysux02-adminkeysbridge11f" in html
    assert "admin_client_requests.js?v=admindirectplan07-adminclientreqbridge11f" in html


def test_admin_integration_key_bridge_does_not_create_new_key_lifecycle() -> None:
    combined = (
        _read("processual_api/static/js/admin_client_requests.js")
        + "\n"
        + _read("processual_api/static/js/admin_api_keys.js")
    )

    assert "service_integration" in combined
    assert "external_partner" not in combined or "service_integration" in combined
    assert "raw_secret_visible: false" in combined
    assert "Production connector approval remains separate" in combined
