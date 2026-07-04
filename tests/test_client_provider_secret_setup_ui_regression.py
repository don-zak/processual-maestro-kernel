from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "processual_api" / "static" / "index.html"
SETTINGS_JS = ROOT / "processual_api" / "static" / "js" / "pages" / "settings.js"
SETTINGS_ROUTER = ROOT / "processual_api" / "routers" / "settings.py"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_provider_secret_setup_controls_exist_in_client_card() -> None:
    html = read_file(INDEX_HTML)

    assert "Provider Connections" in html
    assert "Provider API Key" in html
    assert 'id="set-provider-secret-input"' in html
    assert 'type="password"' in html
    assert 'id="set-provider-secret-test"' in html
    assert 'id="set-provider-secret-save"' in html
    assert 'id="set-provider-secret-clear"' in html
    assert "never displayed after submission" in html


def test_provider_secret_setup_runtime_uses_client_safe_provider_connection_endpoints() -> None:
    js = read_file(SETTINGS_JS)

    assert "function providerSecretSetupPayload()" in js
    assert "function testProviderSecretConnection()" in js
    assert "function saveProviderSecretConnection()" in js
    assert "function clearProviderSecretConnection()" in js
    assert "function initProviderSecretSetupControls()" in js
    assert "provider_secret" in js
    assert "CLIENT.post('/settings/provider-connection/test', body)" in js
    assert "CLIENT.put('/settings/provider-connection/setup', body)" in js
    assert "CLIENT.del('/settings/provider-connection/setup')" in js
    assert "clearProviderSecretInput();" in js


def test_provider_secret_setup_keeps_client_settings_route_boundaries() -> None:
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

    assert "/settings/provider-connection/setup" in js
    assert "/settings/provider-connection/test" in js


def test_provider_secret_setup_backend_exposes_new_client_endpoints() -> None:
    router = read_file(SETTINGS_ROUTER)

    assert "class ClientProviderConnectionSetupPayload" in router
    assert "provider_secret" in router
    assert '@router.put("/provider-connection/setup"' in router
    assert '@router.post("/provider-connection/test"' in router
    assert '@router.delete("/provider-connection/setup"' in router
    assert "_encrypt_api_key(provider_secret, user_id)" in router
    assert "Raw provider secrets are never returned" in router
