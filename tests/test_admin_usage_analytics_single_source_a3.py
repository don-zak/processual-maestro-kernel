from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_usage_monitor_owns_subscription_analytics_host() -> None:
    html = read_text("processual_api/static/admin.html")

    usage_start = html.index('id="page-admin-usage"')
    usage_end = html.index('id="page-admin-program-progress"')
    usage_page = html[usage_start:usage_end]

    assert 'id="admin-subscription-analytics-host"' in usage_page
    assert "Subscription and usage analytics" in usage_page


def test_usage_placeholder_is_removed_when_real_analytics_exists() -> None:
    source = read_text("processual_api/static/js/admin_home_layout.js")

    assert "removeLegacyUsagePlaceholder" in source
    assert "admin-subscription-analytics-host" in source
    assert "Planned usage view:" in source
    assert "evaluations used, evaluations remaining" in source
    assert "PMK_ADMIN_SURFACE_OWNERSHIP_OBSERVER" in source


def test_subscription_analytics_is_read_only() -> None:
    source = read_text("processual_api/static/js/admin_subscription_analytics.js")

    assert "/settings/admin/subscription-analytics" in source
    assert "fetch(ENDPOINT" in source
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert f'method: "{method}"' not in source
        assert f"method: '{method}'" not in source


def test_admin_marketplace_keeps_commercial_activation_ownership() -> None:
    html = read_text("processual_api/static/admin.html")

    marketplace_start = html.index('id="page-admin-marketplace"')
    marketplace_end = html.index('id="page-admin-adapters"')
    marketplace = html[marketplace_start:marketplace_end]

    assert "Subscriptions &amp; Activations" in marketplace
    assert "subscription activations" in marketplace
    assert "admin-subscription-analytics-host" not in marketplace
    assert "/settings/admin/subscription-analytics" not in marketplace


def test_usage_analytics_does_not_mutate_subscription_runtime() -> None:
    source = read_text("processual_api/static/js/admin_subscription_analytics.js")

    forbidden = (
        "activate-subscription",
        "terminate-subscription",
        "suspend-subscription",
        "verify-payment",
        "reconcile-payment",
    )
    for marker in forbidden:
        assert marker not in source
