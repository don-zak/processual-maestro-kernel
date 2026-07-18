from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html")
ADMIN_SUBSCRIPTION_JS = Path("processual_api/static/js/admin_subscription_analytics.js")


def test_admin_subscription_analytics_host_and_script_are_wired():
    html = ADMIN_HTML.read_text(encoding="utf-8")

    assert 'id="admin-subscription-analytics-host"' in html
    assert "admin_subscription_analytics.js?v=adminsubscriptions01f" in html


def test_admin_subscription_analytics_js_uses_real_endpoint_and_admin_auth():
    js = ADMIN_SUBSCRIPTION_JS.read_text(encoding="utf-8")

    assert "/settings/admin/subscription-analytics" in js
    assert "PMK_ADMIN_AUTH" in js
    assert "credentials: \"include\"" in js
    assert "fetch(ENDPOINT" in js


def test_admin_subscription_analytics_js_renders_expected_card_labels():
    js = ADMIN_SUBSCRIPTION_JS.read_text(encoding="utf-8")

    expected_labels = [
        "Subscription &amp; Usage Analytics",
        "Total clients",
        "Active subscriptions",
        "Monthly units used",
        "Monthly allowance",
        "Near quota limit",
        "Quota exceeded",
        "Active API keys",
        "Revoked API keys",
        "Risk indicators",
    ]

    for label in expected_labels:
        assert label in js


def test_admin_subscription_analytics_ui_does_not_render_secret_markers():
    js = ADMIN_SUBSCRIPTION_JS.read_text(encoding="utf-8").lower()

    forbidden = [
        "provider_secret",
        "encrypted_key",
        "raw key",
        "raw_key",
    ]

    for marker in forbidden:
        assert marker not in js

def test_admin_subscription_analytics_host_is_not_inserted_between_scripts():
    html = ADMIN_HTML.read_text(encoding="utf-8")

    host_index = html.index('id="admin-subscription-analytics-host"')
    nearby_before = html[max(0, host_index - 260):host_index].lower()
    nearby_after = html[host_index:host_index + 260].lower()

    assert "<script" not in nearby_before
    assert "</script>" not in nearby_before
    assert "<script" not in nearby_after

def test_admin_subscription_analytics_card_has_local_styles():
    html = ADMIN_HTML.read_text(encoding="utf-8")

    assert 'id="admin-subscription-analytics-style"' in html
    assert ".admin-subscription-analytics-card" in html
    assert ".admin-subscription-analytics-grid" in html
    assert "button[data-admin-subscription-refresh]" in html

def test_admin_subscription_analytics_renders_allowance_not_wired_state():
    js = ADMIN_SUBSCRIPTION_JS.read_text(encoding="utf-8")
    html = ADMIN_HTML.read_text(encoding="utf-8")

    assert "Monthly allowance data is not wired yet for these clients" in js
    assert "Not wired yet" in js
    assert "admin-subscription-analytics-note" in js
    assert "admin-subscription-analytics-summary" in js
    assert ".admin-subscription-analytics-summary" in html
    assert '.admin-subscription-analytics-note[data-state="not-wired"]' in html

def test_admin_subscription_analytics_renders_plan_source_diagnostics():
    js = ADMIN_SUBSCRIPTION_JS.read_text(encoding="utf-8")

    assert "Plan source diagnostics" in js
    assert "plan_sources" in js
    assert "Settings" in js
    assert "Client requests" in js
    assert "Missing" in js
    assert "No verified plan source" in js
    assert "source-of-truth zero" in js
    assert "admin-subscription-analytics-plan-sources" in js


def test_admin_subscription_analytics_cross_links_missing_plan_to_client_usage_summary() -> None:
    from pathlib import Path

    source = Path("processual_api/static/js/admin_subscription_analytics.js").read_text(
        encoding="utf-8"
    )
    html = Path("processual_api/static/admin.html").read_text(encoding="utf-8")

    assert "Client usage summaries will show zero allowance" in source
    assert "verified plan source is stored" in source
    assert "approve and complete a client request" in source
    assert "source-of-truth zero" not in source or "Client usage summaries" in source
    assert "adminsubscriptions01f" in html
