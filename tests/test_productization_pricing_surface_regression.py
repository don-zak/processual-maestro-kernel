from __future__ import annotations

from processual_api.billing.usage_pricing import BILLING_POLICY, PRICING_VERSION
from processual_api.services.client_usage_summary import build_client_usage_summary


def test_client_usage_summary_exposes_pricing_surface() -> None:
    summary = build_client_usage_summary(
        user_id="client-pricing-surface",
        client_id="client-pricing-surface",
        ledger_summary={},
        raw_settings={
            "approved_plan": "enterprise",
            "plan_source": "settings",
            "plan_applied": True,
            "subscription": {"plan_id": "enterprise", "plan": "enterprise"},
        },
    )

    assert summary["pricing_version"] == PRICING_VERSION
    assert summary["billing_policy"] == BILLING_POLICY
    assert summary["plan"]["plan_id"] == "enterprise"
    assert summary["plan"]["source"] == "settings"
    assert summary["plan"]["monthly_unit_allowance"] > 0


def test_client_settings_ui_renders_pricing_surface_tokens() -> None:
    script = open("processual_api/static/js/pages/settings.js", encoding="utf-8").read()

    assert "pricingVersion:" in script
    assert "billingPolicy:" in script
    assert "pricing_version=" in script
    assert "billing_policy=" in script
    assert "summary.pricing_version" in script
    assert "summary.billing_policy" in script
