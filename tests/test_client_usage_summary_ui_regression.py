from pathlib import Path

INDEX_HTML = Path("processual_api/static/index.html")
SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _settings_page_html() -> str:
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index("<!-- ===== PAGE: Settings ===== -->")
    end = text.index("</div><!-- /content -->", start)
    return text[start:end]


def test_client_usage_summary_card_uses_existing_settings_ui() -> None:
    html = _settings_page_html()

    assert 'id="set-usage-summary-card"' in html
    assert "card settings-section" in html
    assert "settings-grid" in html
    assert "inp-group" in html
    assert "mono-block" in html
    assert "Usage &amp; Quotas" in html


def test_client_usage_summary_card_exposes_client_safe_fields() -> None:
    html = _settings_page_html()

    markers = (
        "set-usage-plan",
        "set-usage-quota-used",
        "set-usage-quota-remaining",
        "set-usage-total-units",
        "set-usage-rejected-requests",
        "set-usage-latest-status",
        "BYOK: provider_cost_included=false",
        "Rejected requests are tracked separately",
    )
    for marker in markers:
        assert marker in html


def test_client_usage_summary_script_uses_client_endpoint_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "/settings/usage-summary" in js
    assert "loadUsageSummary" in js
    assert "applyUsageSummary" in js

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/settings/notifications",
        "/admin",
        "admin_",
    )
    for marker in forbidden:
        assert marker not in js


def test_client_usage_summary_script_handles_empty_and_rejected_usage() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "formatNumber" in js
    assert "No recent usage" in js
    assert "Usage summary unavailable" in js
    assert "quota_rejected" in js
    assert "Rejected" in js
