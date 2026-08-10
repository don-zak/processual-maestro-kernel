from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_client_billing_component_has_complete_statement_journey():
    source = _text(STATIC / "js" / "settings_billing_statements.js")

    required = (
        "/billing/statements",
        "Billing & usage",
        "Understand every Maestro Unit",
        "Statement history",
        "Usage breakdown",
        "Additional packages",
        "Copy SHA-256",
        "Download PDF",
        "SHA-256 verified",
        "additional_packages",
        "usage_percent",
        "remaining_units",
        "consumed_units",
        "aria-live",
        "aria-label",
        "focus-visible",
        "@media(max-width:900px)",
        "event.key === 'Enter'",
        "event.key === ' '",
    )
    for marker in required:
        assert marker in source

    forbidden = (
        "provider_secret",
        "encrypted_key",
        "api_key_secret",
        "raw_secret",
    )
    for marker in forbidden:
        assert marker not in source


def test_client_settings_bootstraps_billing_component():
    source = _text(STATIC / "js" / "app.js")
    assert "settings_billing_statements.js" in source
    assert "PMK_SETTINGS_BILLING_STATEMENTS?.init?.()" in source
    assert "Account, provider, plan, billing, integration" in source


def test_supervisor_billing_workspace_has_search_issue_verify_and_pdf():
    source = _text(STATIC / "js" / "admin_billing_statements.js")

    required = (
        "/billing/admin/statements",
        "Customer Billing Statements",
        "Client UUID",
        "Billing period",
        "Search",
        "Issue statement",
        "Statement history",
        "Additional packages",
        "Usage reconciliation",
        "Add-on reconciliation",
        "Copy SHA-256",
        "Download PDF",
        "aria-live",
        "aria-label",
        "focus-visible",
        "@media(max-width:980px)",
        "e.key === 'Enter'",
        "e.key === ' '",
    )
    for marker in required:
        assert marker in source

    assert "PMK_ADMIN_AUTH" in source
    assert "credentials: 'include'" in source


def test_admin_analytics_bootstraps_billing_workspace():
    source = _text(STATIC / "js" / "admin_subscription_analytics.js")
    assert "admin_billing_statements.js" in source
    assert "data-admin-billing-statements" in source
    assert "bootstrapBillingStatements()" in source


def test_billing_components_use_progressive_disclosure_not_raw_debug_dumps():
    client_source = _text(
        STATIC / "js" / "settings_billing_statements.js"
    )
    admin_source = _text(
        STATIC / "js" / "admin_billing_statements.js"
    )

    for source in (client_source, admin_source):
        assert "JSON.stringify(state.selected" not in source
        assert "innerHTML = JSON.stringify" not in source
        assert "purchase_ref" in source
        assert ".slice(0, 12)" in source or ".slice(0,12)" in source
