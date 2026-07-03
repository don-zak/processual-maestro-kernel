from __future__ import annotations

from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_readiness_card_uses_existing_client_ui() -> None:
    html = _settings_page_html()

    assert 'id="set-client-readiness-card"' in html
    assert "Operational Readiness" in html
    assert "Client launch checklist" in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html


def test_client_readiness_card_has_expected_status_markers() -> None:
    html = _settings_page_html()

    markers = (
        "set-readiness-score",
        "set-readiness-next-step",
        "set-readiness-account",
        "set-readiness-plan",
        "set-readiness-integration",
        "set-readiness-provider",
        "set-readiness-checklist",
        "set-readiness-support",
        "Prepare readiness support request",
    )
    for marker in markers:
        assert marker in html


def test_client_readiness_script_aggregates_existing_client_state() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    markers = (
        "readinessState",
        "updateClientReadiness",
        "integrationReadiness",
        "providerReadiness",
        "requestsReadiness",
        "nextReadinessStep",
        "prepareReadinessSupportRequest",
        "set-readiness-score",
        "set-readiness-checklist",
    )
    for marker in markers:
        assert marker in js


def test_client_readiness_uses_existing_safe_workflows_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "/settings/usage-summary" in js
    assert "/settings/api-key-integration" in js
    assert "/settings/provider-connection" in js
    assert "/settings/client-requests" in js

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/applications",
        "/billing/checkout",
        "/billing/portal",
        "/admin",
        "admin_",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in js
