from __future__ import annotations

from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_settings_has_section_collapse_controls() -> None:
    html = _settings_page_html()

    assert 'id="set-section-collapse-controls"' in html
    assert "Settings Sections" in html
    assert "Collapse sections to keep the client settings page compact" in html
    assert 'id="set-sections-expand"' in html
    assert 'id="set-sections-collapse"' in html
    assert 'id="set-sections-collapse-status"' in html


def test_client_settings_collapsible_script_uses_generic_section_behavior() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    markers = (
        "initCollapsibleSettingsSections",
        "setSettingsSectionCollapsed",
        "collapseSettingsSections",
        "settingsSectionBodyNodes",
        "data-settings-section-toggle",
        "set-client-readiness-card",
        "Collapsed non-readiness sections",
        "Expanded all sections",
    )
    for marker in markers:
        assert marker in js


def test_client_settings_collapsible_behavior_does_not_call_backend_or_admin() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    collapsible_slice = js[js.index("function settingsSectionBodyNodes"):js.index("async function loadClientSettings")]

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
        "api_key",
        "encrypted_key",
    )
    for marker in forbidden:
        assert marker not in collapsible_slice


def test_client_settings_sections_remain_existing_cards() -> None:
    html = _settings_page_html()

    expected_cards = (
        'id="set-client-readiness-card"',
        'id="set-api-key-integration-card"',
        'id="set-provider-connection-card"',
        'id="set-client-requests-card"',
        'id="set-client-support-card"',
    )
    for marker in expected_cards:
        assert marker in html

    assert html.count("settings-section") >= 7
