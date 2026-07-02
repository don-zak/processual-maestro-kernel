from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
APP_JS = Path("processual_api/static/js/app.js")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("<!-- ===== PAGE: Adapters ===== -->")
    return text[start:end]


def test_console_settings_is_client_settings_shell() -> None:
    html = _settings_page_html()

    assert "Client Settings" in html
    assert "Account" in html
    assert "Preferences" in html
    assert "Plan and Usage" in html
    assert "Provider Connections" in html
    assert "Support" in html


def test_client_settings_page_does_not_expose_admin_controls() -> None:
    html = _settings_page_html()

    forbidden = (
        "LLM Provider for Reports",
        "Discord Webhook",
        "API Keys",
        "set-apikey",
        "set-llm",
        "Generate New Key",
    )
    for marker in forbidden:
        assert marker not in html


def test_client_settings_script_does_not_call_admin_endpoints() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    forbidden = (
        "/settings/api-keys",
        "loadApiKeys",
        "set-apikey",
        "set-llm",
        "/settings/llm-provider",
        "/settings/notifications",
    )
    for marker in forbidden:
        assert marker not in js


def test_client_settings_keeps_safe_client_preferences_and_subscription() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    app = APP_JS.read_text(encoding="utf-8")

    assert "/settings/general" in js
    assert "/settings/subscription" in js
    assert "set-general-save" in js
    assert "Client Settings" in app
