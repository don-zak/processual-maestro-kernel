from __future__ import annotations

from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_enterprise_api_key_integration_card_is_hidden_by_default() -> None:
    html = _settings_page_html()

    assert 'id="set-api-key-integration-card"' in html
    assert 'style="display:none"' in html
    assert "API Key Integration" in html
    assert "Enterprise-only client integration status" in html


def test_enterprise_api_key_integration_uses_existing_client_ui_classes() -> None:
    html = _settings_page_html()

    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html
    assert "No integration keys issued yet" in html


def test_enterprise_api_key_integration_fields_are_client_safe() -> None:
    html = _settings_page_html()

    markers = (
        "set-api-key-integration-plan",
        "set-api-key-integration-status",
        "set-api-key-integration-count",
        "set-api-key-integration-scopes",
        "set-api-key-integration-keys",
        "Raw secret keys are never displayed after creation",
    )
    for marker in markers:
        assert marker in html


def test_enterprise_api_key_integration_script_uses_client_safe_endpoint() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "/settings/api-key-integration" in js
    assert "loadApiKeyIntegration" in js
    assert "applyApiKeyIntegration" in js
    assert "renderIntegrationKeys" in js
    assert "card.style.display = enabled ? '' : 'none'" in js

    forbidden = (
        "/settings/api-keys",
        "/admin",
        "admin_",
        ".api_key",
        "api_key:",
        "hashed",
        "hashed_key",
    )
    for marker in forbidden:
        assert marker not in js
