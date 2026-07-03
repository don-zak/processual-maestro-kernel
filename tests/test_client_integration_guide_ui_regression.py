from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_integration_guide_card_is_collapsible_settings_section() -> None:
    html = _settings_page_html()

    assert 'id="set-client-integration-guide-card"' in html
    assert "Client Integration Guide" in html
    assert "Copy-safe setup notes" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "mono-block" in html


def test_client_integration_guide_card_uses_placeholders_and_safe_actions() -> None:
    html = _settings_page_html()

    markers = (
        "set-guide-base-url",
        "set-guide-output",
        "set-guide-copy-quickstart",
        "set-guide-copy-checklist",
        "set-guide-support",
        "&lt;maestro-base-url&gt;",
        "&lt;client-integration-key&gt;",
        "Do not paste raw provider secrets",
        "Prepare integration support request",
    )
    for marker in markers:
        assert marker in html


def test_client_integration_guide_script_is_client_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    markers = (
        "clientIntegrationGuideText",
        "copyClientIntegrationGuide",
        "prepareIntegrationGuideSupportRequest",
        "initClientIntegrationGuide",
        "set-guide-base-url",
        "set-guide-output",
        "provider_setup_help",
        "copy-safe integration guide",
    )
    for marker in markers:
        assert marker in js

    guide_slice = js[
        js.index("function clientIntegrationGuideText"):
        js.index("function settingsSectionBodyNodes")
    ]

    forbidden = (
        "CLIENT.get",
        "CLIENT.post",
        "CLIENT.put",
        "CLIENT.delete",
        "/admin",
        "/applications",
        "/billing/checkout",
        "/billing/portal",
        "/settings/api-keys",
        "/settings/llm-provider",
        "encrypted_key",
    )
    for marker in forbidden:
        assert marker not in guide_slice


def test_client_integration_guide_is_initialized_before_collapsible_sections() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "initClientIntegrationGuide();" in js
    assert "initCollapsibleSettingsSections();" in js
    assert js.index("initClientIntegrationGuide();") < js.index(
        "initCollapsibleSettingsSections();"
    )
