from pathlib import Path

STATIC = Path("processual_api/static")
NAV = STATIC / "js" / "admin_nav.js"
DASHBOARD_JS = STATIC / "js" / "admin_marketplace_dashboard.js"
DASHBOARD_CSS = STATIC / "css" / "admin_marketplace_dashboard.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_nav_loads_dashboard_as_isolated_assets() -> None:
    nav = _read(NAV)

    assert "bootstrapIntegrationCenter18" in nav
    assert "bootstrapAdminGovernance" in nav
    assert "bootstrapAdminMarketplaceDashboard" in nav
    assert "/console/js/admin_marketplace_dashboard.js?v=a3-ops-1" in nav
    assert "/console/css/admin_marketplace_dashboard.css?v=a3-ops-1" in nav
    assert "page-admin-marketplace" in nav


def test_dashboard_renders_remaining_admin_marketplace_observability_scope() -> None:
    script = _read(DASHBOARD_JS)

    assert "Commercial Operations" in script
    assert "Trials" in script
    assert "Subscriptions" in script
    assert "Usage vs quotas" in script
    assert "Channel governance" in script
    assert "Verified order value" in script
    assert "/admin-marketplace/dashboard" in script
    assert "PMK_ADMIN_AUTH" in script
    assert "credentials: 'include'" in script
    assert "escapeHtml" in script
    assert "admin_review_required" in script
    assert "selected_channel" in script
    assert "remaining_units" in script


def test_dashboard_does_not_claim_accounting_revenue_or_render_sensitive_material() -> None:
    script = _read(DASHBOARD_JS)
    normalized = script.lower()

    assert "not an accounting revenue-recognition statement" in normalized
    assert "raw_account_identifier" not in normalized
    assert "source_reference_hash" not in normalized
    assert "payload_ciphertext" not in normalized
    assert "verification_token" not in normalized
    assert "completion_token" not in normalized


def test_dashboard_layout_is_responsive() -> None:
    css = _read(DASHBOARD_CSS)

    assert ".am-ops-dashboard" in css
    assert ".am-ops-grid" in css
    assert "@media (max-width: 900px)" in css
    assert "@media (max-width: 600px)" in css
