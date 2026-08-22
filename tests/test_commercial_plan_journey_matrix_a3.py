from __future__ import annotations

from decimal import Decimal

import pytest

from processual_api.billing.maestro_group1_selected_pricing import (
    DEFAULT_YEARLY_DISCOUNT_PERCENT,
)
from processual_api.billing.public_plan_journey import (
    ANNUAL_DISCOUNT_PERCENT,
    PLAN_DEFINITIONS,
    PUBLIC_PLAN_ORDER,
    public_plan_journey_catalog,
)

CATALOG = public_plan_journey_catalog()
PLANS = {plan["plan_id"]: plan for plan in CATALOG["plans"]}


def test_public_plan_catalog_has_unique_complete_order() -> None:
    assert tuple(PLANS) == PUBLIC_PLAN_ORDER
    assert len(PLANS) == len(PUBLIC_PLAN_ORDER)
    assert CATALOG["billing_periods"] == ["monthly", "annual"]
    assert CATALOG["annual_discount_percent"] == int(ANNUAL_DISCOUNT_PERCENT)
    assert CATALOG["annual_discount_scope"] == "eligible_public_base_plans_only"
    assert CATALOG["checkout_enabled"] is False


def test_public_journey_uses_selected_pricing_discount_authority() -> None:
    assert ANNUAL_DISCOUNT_PERCENT == DEFAULT_YEARLY_DISCOUNT_PERCENT
    assert Decimal(str(CATALOG["annual_discount_percent"])) == DEFAULT_YEARLY_DISCOUNT_PERCENT


@pytest.mark.parametrize("plan_id", PUBLIC_PLAN_ORDER)
def test_every_plan_matches_its_authoritative_definition(plan_id: str) -> None:
    plan = PLANS[plan_id]
    definition = PLAN_DEFINITIONS[plan_id]

    assert plan["display_name"] == definition["display_name"]
    assert plan["account_type"] == definition["account_type"]
    assert plan["requires_assessment"] is bool(definition["requires_assessment"])
    assert plan["features"] == definition["features"]
    assert plan["trial"] == definition["trial"]
    assert plan["byok"]["required"] is True
    assert plan["byok"]["provider_cost_included"] is False


@pytest.mark.parametrize("plan_id", PUBLIC_PLAN_ORDER)
def test_each_plan_has_exactly_one_safe_entry_path(plan_id: str) -> None:
    plan = PLANS[plan_id]

    if plan["requires_assessment"]:
        assert plan["action"] == "request_assessment"
        assert plan["registration_available"] is False
        assert plan["registration_path"] is None
        assert plan["monthly_price_usd"] is None
        assert plan["annual_price_usd"] is None
        assert plan["included_quota_units"] is None
    else:
        assert plan["action"] == "start_registration"
        assert plan["registration_available"] is True
        assert plan["registration_path"] == f"/register/{plan['account_type']}"
        assert plan["monthly_price_usd"] is not None
        assert plan["annual_price_usd"] is not None
        assert plan["included_quota_units"] is not None
        assert plan["included_quota_units"] > 0


def test_annual_prices_apply_the_declared_base_plan_discount() -> None:
    multiplier = Decimal("1") - DEFAULT_YEARLY_DISCOUNT_PERCENT / Decimal("100")

    for plan in PLANS.values():
        if plan["monthly_price_usd"] is None:
            continue

        monthly = Decimal(plan["monthly_price_usd"])
        annual = Decimal(plan["annual_price_usd"])
        expected = (monthly * Decimal("12") * multiplier).quantize(Decimal("0.01"))

        assert annual == expected
        assert plan["annual_discount_percent"] == int(DEFAULT_YEARLY_DISCOUNT_PERCENT)
        assert plan["quota_add_ons_policy"]["annual_discount_applies"] is False


def test_quota_add_ons_never_mutate_the_base_subscription_period() -> None:
    for plan in PLANS.values():
        for add_on in plan["quota_add_ons"]:
            assert add_on["billing_model"] == "on_demand"
            assert add_on["recurring"] is False
            assert add_on["annual_discount_percent"] == 0
            assert add_on["requires_active_subscription"] is True
