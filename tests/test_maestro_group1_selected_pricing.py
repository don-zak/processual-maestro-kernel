from decimal import Decimal

import pytest

from processual_api.billing.maestro_group1_pricing_review import (
    PricingReviewValidationError,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    ENTERPRISE_VOLUME_ADJUSTMENTS_PERCENT,
    SELECTED_MONTHLY_PRICES,
    SELECTED_OVERAGE_PRICES_PER_1000_UNITS,
    build_selected_pricing_proposal,
    calculate_selected_plan_proposal,
)


def test_selected_monthly_prices_match_adopted_proposal() -> None:
    assert SELECTED_MONTHLY_PRICES == {
        "academic": Decimal("29"),
        "starter": Decimal("49"),
        "enterprise_integration_starter": Decimal("259"),
        "business": Decimal("519"),
        "enterprise_pilot": Decimal("2790"),
        "enterprise_core": Decimal("7890"),
        "enterprise_scale": Decimal("14990"),
        "enterprise_strategic": Decimal("23900"),
    }


def test_enterprise_volume_adjustments_are_explicit_and_bounded() -> None:
    assert ENTERPRISE_VOLUME_ADJUSTMENTS_PERCENT == {
        "enterprise_pilot": Decimal("0"),
        "enterprise_core": Decimal("6"),
        "enterprise_scale": Decimal("10"),
        "enterprise_strategic": Decimal("14"),
    }
    assert all(Decimal("0") <= value <= Decimal("20") for value in ENTERPRISE_VOLUME_ADJUSTMENTS_PERCENT.values())


def test_selected_prices_never_cross_calculated_minimum() -> None:
    for plan_id in SELECTED_MONTHLY_PRICES:
        proposal = calculate_selected_plan_proposal(plan_id)
        assert proposal.selected_monthly_price >= (proposal.calculated_minimum_monthly_price)


def test_enterprise_price_per_unit_decreases_with_scale() -> None:
    enterprise_ids = (
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    )
    per_unit = []
    for plan_id in enterprise_ids:
        proposal = calculate_selected_plan_proposal(plan_id)
        per_unit.append(proposal.selected_monthly_price / Decimal(proposal.monthly_unit_allowance))
    assert per_unit == sorted(per_unit, reverse=True)


def test_selected_overage_prices_are_present() -> None:
    assert set(SELECTED_OVERAGE_PRICES_PER_1000_UNITS) == set(SELECTED_MONTHLY_PRICES)
    assert all(value > Decimal("0") for value in SELECTED_OVERAGE_PRICES_PER_1000_UNITS.values())


def test_selected_proposal_remains_non_commercial() -> None:
    payload = build_selected_pricing_proposal()
    assert payload["proposal_status"] == "draft_review"
    assert payload["basis_scenario"] == "recommended"
    assert payload["byok_only"] is True
    assert payload["provider_cost_included"] is False
    assert payload["approved_for_quota"] is False
    assert payload["approved_for_pricing"] is False
    assert payload["approved_for_invoicing"] is False
    assert payload["approved_for_checkout"] is False
    assert payload["approved_for_settlement"] is False


def test_unknown_plan_fails_closed() -> None:
    with pytest.raises(PricingReviewValidationError):
        calculate_selected_plan_proposal("unknown")
