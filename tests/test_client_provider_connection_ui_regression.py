from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_provider_connection_card_uses_existing_client_ui() -> None:
    html = _settings_page_html()

    assert 'id="set-provider-connection-card"' in html
    assert "Provider Connections" in html
    assert "Client BYOK provider status" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html


def test_provider_connection_card_exposes_client_safe_status_fields() -> None:
    html = _settings_page_html()

    markers = (
        "set-provider-connection-status",
        "set-provider-connection-provider",
        "set-provider-connection-model",
        "set-provider-connection-cost",
        "set-provider-connection-providers",
        "set-provider-connection-note",
        "Raw provider secrets are never displayed",
    )
    for marker in markers:
        assert marker in html


def test_provider_connection_script_uses_client_safe_endpoint_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "/settings/provider-connection" in js
    assert "loadProviderConnection" in js
    assert "applyProviderConnection" in js

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
