from decimal import Decimal

import pytest

from processual_api.billing.maestro_calibration_contracts import (
    CalibrationQuantities,
    MaestroResourceBand,
)
from processual_api.billing.maestro_group1_pricing_review import (
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_PRICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_SETTLEMENT,
    BYOK_ONLY,
    COMMERCIAL_ENFORCEMENT_ENABLED,
    ENTERPRISE_CORE_UNIT_ALLOWANCE,
    ENTERPRISE_PILOT_UNIT_ALLOWANCE,
    ENTERPRISE_SCALE_UNIT_ALLOWANCE,
    ENTERPRISE_STRATEGIC_UNIT_ALLOWANCE,
    PLAN_REVIEW_CONFIG,
    PROVIDER_COST_INCLUDED,
    REVIEW_SCENARIOS,
    CommercialValueBand,
    PricingReviewValidationError,
    PricingScenarioName,
    UnitCostScenario,
    build_group1_price_review,
    calculate_maestro_units,
    calculate_plan_pricing,
)


def test_group1_review_remains_non_commercial() -> None:
    assert BYOK_ONLY is True
    assert PROVIDER_COST_INCLUDED is False
    assert COMMERCIAL_ENFORCEMENT_ENABLED is False
    assert APPROVED_FOR_QUOTA is False
    assert APPROVED_FOR_PRICING is False
    assert APPROVED_FOR_INVOICING is False
    assert APPROVED_FOR_CHECKOUT is False
    assert APPROVED_FOR_SETTLEMENT is False


def test_unit_weights_match_reference_calibration_examples() -> None:
    assert calculate_maestro_units(CalibrationQuantities(base_executions=Decimal("1"))).raw_units == Decimal("1.0000")
    assert calculate_maestro_units(CalibrationQuantities(integration_actions=Decimal("4"))).raw_units == Decimal(
        "1.0000"
    )
    assert calculate_maestro_units(CalibrationQuantities(equivalent_pages=Decimal("50"))).raw_units == Decimal("2.0000")
    assert calculate_maestro_units(CalibrationQuantities(records_processed=Decimal("1000"))).raw_units == Decimal(
        "1.0000"
    )
    assert calculate_maestro_units(CalibrationQuantities(verification_items=Decimal("25"))).raw_units == Decimal(
        "1.0000"
    )


def test_resource_bands_and_custom_review() -> None:
    quantities = CalibrationQuantities(
        base_executions=Decimal("1"),
        integration_actions=Decimal("4"),
    )
    assert calculate_maestro_units(
        quantities,
        MaestroResourceBand.HEAVY,
    ).settled_units == Decimal("2.5000")
    assert calculate_maestro_units(
        quantities,
        MaestroResourceBand.EXTREME,
    ).settled_units == Decimal("3.0000")
    custom = calculate_maestro_units(
        quantities,
        MaestroResourceBand.CUSTOM,
    )
    assert custom.settled_units is None
    assert custom.manual_review_required is True


def test_recommended_scenario_uses_margin_and_uniqueness() -> None:
    scenario = next(item for item in REVIEW_SCENARIOS if item.name is PricingScenarioName.RECOMMENDED)
    assert scenario.target_net_margin_percent == Decimal("40")
    assert scenario.uniqueness_premium_percent == Decimal("10")
    assert scenario.uniqueness_adjusted_price_per_unit > (scenario.minimum_sale_price_per_unit)


def test_commercial_value_band_changes_recommended_price() -> None:
    scenario = next(item for item in REVIEW_SCENARIOS if item.name is PricingScenarioName.RECOMMENDED)
    standard = calculate_plan_pricing(
        "standard",
        10_000,
        scenario,
        CommercialValueBand.STANDARD,
    )
    enterprise = calculate_plan_pricing(
        "enterprise",
        10_000,
        scenario,
        CommercialValueBand.ENTERPRISE_GOVERNED,
    )
    assert enterprise.recommended_monthly_price > (standard.recommended_monthly_price)


def test_plan_pricing_remains_review_only() -> None:
    scenario = next(item for item in REVIEW_SCENARIOS if item.name is PricingScenarioName.RECOMMENDED)
    review = calculate_plan_pricing(
        "starter",
        10_000,
        scenario,
        CommercialValueBand.STANDARD,
    )
    assert review.estimated_monthly_cost > Decimal("0")
    assert review.minimum_monthly_price > review.estimated_monthly_cost
    assert review.recommended_monthly_price >= review.minimum_monthly_price
    assert review.overage_price_per_1000_units > Decimal("0")
    assert review.price_status == "draft_review"
    assert review.approved_for_checkout is False


def test_review_contains_all_plans_and_scenarios() -> None:
    payload = build_group1_price_review()
    assert payload["pricing_status"] == "draft_review"
    assert payload["currency"] == "USD"
    assert payload["provider_cost_included"] is False
    assert payload["approved_for_pricing"] is False
    assert payload["approved_for_checkout"] is False
    assert len(payload["plans"]) == (len(PLAN_REVIEW_CONFIG) * len(REVIEW_SCENARIOS))
    assert {item["plan_id"] for item in payload["plans"]} == set(PLAN_REVIEW_CONFIG)


def test_invalid_cost_scenario_fails_closed() -> None:
    with pytest.raises(PricingReviewValidationError):
        UnitCostScenario(
            name=PricingScenarioName.RECOMMENDED,
            infrastructure_cost_per_unit=Decimal("0.01"),
            operations_cost_per_unit=Decimal("0.01"),
            support_cost_per_unit=Decimal("0.01"),
            fixed_cost_allocation_per_unit=Decimal("0.01"),
            retry_failure_overhead_percent=Decimal("10"),
            risk_reserve_percent=Decimal("10"),
            processor_percent=Decimal("40"),
            tax_reserve_percent=Decimal("20"),
            target_net_margin_percent=Decimal("40"),
            uniqueness_premium_percent=Decimal("10"),
        )


def test_float_costs_are_rejected() -> None:
    with pytest.raises(PricingReviewValidationError):
        UnitCostScenario(
            name=PricingScenarioName.RECOMMENDED,
            infrastructure_cost_per_unit=0.01,  # type: ignore[arg-type]
            operations_cost_per_unit=Decimal("0.01"),
            support_cost_per_unit=Decimal("0.01"),
            fixed_cost_allocation_per_unit=Decimal("0.01"),
            retry_failure_overhead_percent=Decimal("10"),
            risk_reserve_percent=Decimal("10"),
            processor_percent=Decimal("5"),
            tax_reserve_percent=Decimal("10"),
            target_net_margin_percent=Decimal("40"),
            uniqueness_premium_percent=Decimal("10"),
        )


def test_enterprise_plan_ladder_is_reference_policy() -> None:
    assert ENTERPRISE_PILOT_UNIT_ALLOWANCE == 500_000
    assert ENTERPRISE_CORE_UNIT_ALLOWANCE == 1_500_000
    assert ENTERPRISE_SCALE_UNIT_ALLOWANCE == 3_000_000
    assert ENTERPRISE_STRATEGIC_UNIT_ALLOWANCE == 5_000_000

    assert PLAN_REVIEW_CONFIG["enterprise_pilot"][0] == 500_000
    assert PLAN_REVIEW_CONFIG["enterprise_core"][0] == 1_500_000
    assert PLAN_REVIEW_CONFIG["enterprise_scale"][0] == 3_000_000
    assert PLAN_REVIEW_CONFIG["enterprise_strategic"][0] == 5_000_000
    assert "enterprise" not in PLAN_REVIEW_CONFIG


def test_enterprise_tiers_are_not_seat_based() -> None:
    adopted_enterprise_tier_ids = {
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    }
    enterprise_tiers = {key: PLAN_REVIEW_CONFIG[key] for key in adopted_enterprise_tier_ids}
    assert set(enterprise_tiers) == adopted_enterprise_tier_ids
    for allowance, value_band in enterprise_tiers.values():
        assert allowance > 0
        assert value_band is CommercialValueBand.ENTERPRISE_GOVERNED
