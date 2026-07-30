from pathlib import Path

PRICING_HTML = Path("processual_api/static/pricing.html")
PLAN_DETAIL_HTML = Path("processual_api/static/plan_detail.html")


def test_pricing_index_does_not_duplicate_pricing_factor_details() -> None:
    source = PRICING_HTML.read_text(encoding="utf-8")
    assert 'id="pricing-plan-grid"' in source
    assert 'href="/plans/${id}"' in source
    assert 'id="pricing-factors-toggle"' not in source
    assert 'fetch("/billing/unit-cost-assumptions"' not in source


def test_plan_detail_exposes_public_policy_without_internal_values() -> None:
    source = PLAN_DETAIL_HTML.read_text(encoding="utf-8").lower()
    assert "byok only" in source
    assert "provider usage is outside the maestro subscription" in source
    assert "unused units roll over" in source
    assert "never become cash credit" in source
    for marker in (
        "target_margin",
        "minimum_price_cents",
        "recommended_price_cents",
        "risk_buffer_cents",
        "local_tax_reserve_cents",
        "processor_percent",
        "processor_fixed_fee_cents",
        "server_or_cloud_run_cost_cents",
        "database_cost_cents",
        "cache_cost_cents",
        "storage_cost_cents",
        "egress_cost_cents",
    ):
        assert marker not in source


def test_plan_index_actions_are_consistent_and_accessible() -> None:
    source = PRICING_HTML.read_text(encoding="utf-8")
    assert ".plan-card{" in source
    assert "min-height:210px" in source
    assert ".plan-card:hover,.plan-card:focus-visible" in source
    assert "prefers-reduced-motion" in source
