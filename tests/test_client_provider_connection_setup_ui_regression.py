from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "processual_api" / "static" / "index.html"
SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_provider_connection_setup_request_controls_exist() -> None:
    html = read_file(INDEX_HTML)

    assert "Provider Connections" in html
    assert 'id="set-provider-setup-request"' in html
    assert 'id="set-provider-setup-provider"' in html
    assert 'id="set-provider-setup-model"' in html
    assert 'id="set-provider-setup-request-prepare"' in html
    assert 'id="set-provider-setup-request-status"' in html
    assert 'id="set-provider-connection-last-tested"' in html
    assert 'id="set-provider-connection-secret-status"' in html
    assert "Raw provider secrets are never displayed" in html
    assert "Do not paste provider secrets here" in html


def test_provider_connection_setup_request_uses_client_request_workflow() -> None:
    js = read_file(SETTINGS_JS)

    assert "function providerSetupRequestPayload()" in js
    assert "function providerSetupRequestMessage()" in js
    assert "function prepareProviderSetupRequest()" in js
    assert "function initProviderSetupRequestControls()" in js
    assert "prepareClientSupportRequest(" in js
    assert "provider_setup_help" in js
    assert "set-provider-setup-request-prepare" in js
    assert "initProviderSetupRequestControls();" in js


def test_provider_connection_setup_request_keeps_client_safety_boundaries() -> None:
    js = read_file(SETTINGS_JS)

    forbidden = (
        "/settings/llm-provider",
        "/settings/api-keys",
        "/admin",
        "admin_",
        "set-llm",
        "encrypted_key",
        "api_key",
    )

    for marker in forbidden:
        assert marker not in js

    assert "/settings/provider-connection" in js
    assert "/settings/client-request" in js
