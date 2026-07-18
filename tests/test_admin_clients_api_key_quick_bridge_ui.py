from pathlib import Path

ADMIN_CLIENT_REQUESTS_JS = Path("processual_api/static/js/admin_client_requests.js")


def test_admin_clients_page_has_visible_api_key_quick_bridge() -> None:
    js = ADMIN_CLIENT_REQUESTS_JS.read_text(encoding="utf-8")
    markers = (
        "renderAdminClientApiKeysQuickBridge",
        "admin-client-api-keys-quick-bridge",
        "admin-client-open-api-keys-panel",
        "Integration API Keys",
        "Open Integration API Keys",
        "admin_clients_quick_bridge",
        "renderAdminClientApiKeysQuickBridge(card)",
    )
    for marker in markers:
        assert marker in js


def test_admin_clients_quick_bridge_preserves_security_guardrails() -> None:
    js = ADMIN_CLIENT_REQUESTS_JS.read_text(encoding="utf-8")
    assert "production_connector_approved: false" in js
    assert "raw_secret_visible: false" in js
    assert "No raw secret is shown" in js
    assert "no production connector is approved" in js
    assert "pmk-admin-integration-key-bridge" in js
    assert "runtime_connector_approved: true" not in js
