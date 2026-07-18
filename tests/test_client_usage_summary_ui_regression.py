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
        "set-usage-monthly-included-units",
        "set-usage-quota-status",
        "set-usage-current-period",
        "set-usage-latest-usage-at",
        "set-usage-review-request",
        "Prepare usage review request",
        "BYOK: provider_cost_included=false",
        "Rejected requests are tracked separately",
    )
    for marker in markers:
        assert marker in html


def test_client_usage_summary_script_uses_client_endpoint_only() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")

    assert "/settings/client/usage-summary" in js
    assert "loadUsageSummary" in js
    assert "applyUsageSummary" in js

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/settings/notifications",
        "/admin",
        "admin_",
        "api_key",
        "encrypted_key",
        "set-llm",
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
    assert "prepareUsageReviewRequest" in js
    assert "billing_usage_review" in js
    assert "monthly_included_units" in js
    assert "quota_status" in js
    assert "latest_usage_at" in js
    assert "provider_cost_included=false" in js


def test_client_usage_summary_ui_uses_client_scoped_02a_endpoint() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "/settings/client/usage-summary" in js
    assert "set-usage-plan-source" in html
    assert "set-usage-percent" in html
    assert "set-usage-provider-status" in html
    assert "set-usage-recommendations" in html

def test_usage_review_request_uses_client_usage_summary_payload() -> None:
    from pathlib import Path

    source = Path("processual_api/static/js/pages/settings.js").read_text(encoding="utf-8")

    assert "function prepareUsageReviewRequest()" in source
    assert "usageSummaryPlan(summary)" in source
    assert "usageSummaryUsage(summary)" in source
    assert "usageSummaryQuota(summary)" in source
    assert "usageSummaryProvider(summary)" in source

    assert "plan_source=" in source
    assert "monthly_units_used=" in source
    assert "monthly_units_allowance=" in source
    assert "usage_percent=" in source
    assert "provider_connection=" in source
    assert "recommendations=" in source
    assert "billing_usage_review" in source

    legacy_markers = [
        "monthly_included_units=' + formatNumber(summary.monthly_included_units",
        "quota_used=' + formatNumber(summary.quota_used)",
        "total_units=' + formatNumber(summary.total_units)",
    ]
    for marker in legacy_markers:
        assert marker not in source
