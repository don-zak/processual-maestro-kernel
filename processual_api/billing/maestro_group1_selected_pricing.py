"""Selected Maestro Group 1 commercial price proposal.

This module converts the adopted pricing review model into a customer-facing
draft proposal. It does not approve, publish, or enforce prices.

The proposal keeps:
- BYOK-only provider costs excluded;
- the recommended scenario as the calculation basis;
- explicit enterprise volume adjustments;
- minimum-price floor protection;
- checkout, invoicing, settlement, and quota enforcement disabled.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final

from processual_api.billing.maestro_group1_pricing_review import (
    APPROVED_FOR_CHECKOUT,
    APPROVED_FOR_INVOICING,
    APPROVED_FOR_PRICING,
    APPROVED_FOR_QUOTA,
    APPROVED_FOR_SETTLEMENT,
    BYOK_ONLY,
    CURRENCY,
    PLAN_REVIEW_CONFIG,
    PROVIDER_COST_INCLUDED,
    REVIEW_SCENARIOS,
    CommercialValueBand,
    PricingReviewValidationError,
    PricingScenarioName,
    calculate_plan_pricing,
)

SELECTED_PROPOSAL_VERSION: Final = "2026-07-group1-selected-pricing-v1"
SELECTED_PROPOSAL_STATUS: Final = "draft_review"
DEFAULT_YEARLY_DISCOUNT_PERCENT: Final = Decimal("15")

ZERO = Decimal("0")
CENT = Decimal("0.01")
ONE = Decimal("1")
HUNDRED = Decimal("100")

SELECTED_MONTHLY_PRICES: Final[dict[str, Decimal]] = {
    "academic": Decimal("29"),
    "starter": Decimal("49"),
    "enterprise_integration_starter": Decimal("259"),
    "business": Decimal("519"),
    "enterprise_pilot": Decimal("2790"),
    "enterprise_core": Decimal("7890"),
    "enterprise_scale": Decimal("14990"),
    "enterprise_strategic": Decimal("23900"),
}

ENTERPRISE_VOLUME_ADJUSTMENTS_PERCENT: Final[dict[str, Decimal]] = {
    "enterprise_pilot": Decimal("0"),
    "enterprise_core": Decimal("6"),
    "enterprise_scale": Decimal("10"),
    "enterprise_strategic": Decimal("14"),
}

SELECTED_OVERAGE_PRICES_PER_1000_UNITS: Final[dict[str, Decimal]] = {
    "academic": Decimal("6.50"),
    "starter": Decimal("5.90"),
    "enterprise_integration_starter": Decimal("6.00"),
    "business": Decimal("6.00"),
    "enterprise_pilot": Decimal("6.50"),
    "enterprise_core": Decimal("6.20"),
    "enterprise_scale": Decimal("5.95"),
    "enterprise_strategic": Decimal("5.75"),
}


@dataclass(frozen=True, slots=True)
class SelectedPlanProposal:
    plan_id: str
    monthly_unit_allowance: int
    value_band: CommercialValueBand
    calculated_monthly_cost: Decimal
    calculated_minimum_monthly_price: Decimal
    calculated_recommended_monthly_price: Decimal
    enterprise_volume_adjustment_percent: Decimal
    selected_monthly_price: Decimal
    selected_yearly_price: Decimal
    selected_overage_price_per_1000_units: Decimal
    currency: str = CURRENCY
    pricing_status: str = SELECTED_PROPOSAL_STATUS
    approved_for_pricing: bool = False
    approved_for_checkout: bool = False

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise PricingReviewValidationError("plan_id must not be blank")
        if self.monthly_unit_allowance <= 0:
            raise PricingReviewValidationError("monthly_unit_allowance must be positive")
        for field_name in (
            "calculated_monthly_cost",
            "calculated_minimum_monthly_price",
            "calculated_recommended_monthly_price",
            "enterprise_volume_adjustment_percent",
            "selected_monthly_price",
            "selected_yearly_price",
            "selected_overage_price_per_1000_units",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise PricingReviewValidationError(f"{field_name} must be a finite Decimal")
            if value < ZERO:
                raise PricingReviewValidationError(f"{field_name} must not be negative")
        if self.enterprise_volume_adjustment_percent > HUNDRED:
            raise PricingReviewValidationError("enterprise volume adjustment must not exceed 100%")
        if self.selected_monthly_price < self.calculated_minimum_monthly_price:
            raise PricingReviewValidationError("selected monthly price must not fall below calculated minimum")
        if self.pricing_status != "draft_review":
            raise PricingReviewValidationError("selected proposal must remain draft_review")
        if self.approved_for_pricing or self.approved_for_checkout:
            raise PricingReviewValidationError("selected proposal must not activate commercial approval")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["value_band"] = self.value_band.value
        for key, value in tuple(payload.items()):
            if isinstance(value, Decimal):
                payload[key] = str(value)
        return payload


def recommended_scenario():
    return next(scenario for scenario in REVIEW_SCENARIOS if scenario.name is PricingScenarioName.RECOMMENDED)


def calculate_selected_plan_proposal(plan_id: str) -> SelectedPlanProposal:
    if plan_id not in PLAN_REVIEW_CONFIG:
        raise PricingReviewValidationError(f"unknown selected proposal plan: {plan_id}")
    if plan_id not in SELECTED_MONTHLY_PRICES:
        raise PricingReviewValidationError(f"selected monthly price missing for plan: {plan_id}")
    if plan_id not in SELECTED_OVERAGE_PRICES_PER_1000_UNITS:
        raise PricingReviewValidationError(f"selected overage price missing for plan: {plan_id}")

    allowance, value_band = PLAN_REVIEW_CONFIG[plan_id]
    calculated = calculate_plan_pricing(
        plan_id,
        allowance,
        recommended_scenario(),
        value_band,
        yearly_discount_percent=DEFAULT_YEARLY_DISCOUNT_PERCENT,
    )
    selected_monthly_price = SELECTED_MONTHLY_PRICES[plan_id]
    selected_yearly_price = (
        selected_monthly_price * Decimal("12") * (ONE - DEFAULT_YEARLY_DISCOUNT_PERCENT / HUNDRED)
    ).quantize(CENT, rounding=ROUND_HALF_UP)

    return SelectedPlanProposal(
        plan_id=plan_id,
        monthly_unit_allowance=allowance,
        value_band=value_band,
        calculated_monthly_cost=calculated.estimated_monthly_cost,
        calculated_minimum_monthly_price=calculated.minimum_monthly_price,
        calculated_recommended_monthly_price=(calculated.recommended_monthly_price),
        enterprise_volume_adjustment_percent=(ENTERPRISE_VOLUME_ADJUSTMENTS_PERCENT.get(plan_id, ZERO)),
        selected_monthly_price=selected_monthly_price,
        selected_yearly_price=selected_yearly_price,
        selected_overage_price_per_1000_units=(SELECTED_OVERAGE_PRICES_PER_1000_UNITS[plan_id]),
    )


def build_selected_pricing_proposal() -> dict[str, Any]:
    proposals = [calculate_selected_plan_proposal(plan_id).to_dict() for plan_id in SELECTED_MONTHLY_PRICES]
    return {
        "proposal_version": SELECTED_PROPOSAL_VERSION,
        "proposal_status": SELECTED_PROPOSAL_STATUS,
        "currency": CURRENCY,
        "basis_scenario": PricingScenarioName.RECOMMENDED.value,
        "byok_only": BYOK_ONLY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "approved_for_quota": APPROVED_FOR_QUOTA,
        "approved_for_pricing": APPROVED_FOR_PRICING,
        "approved_for_invoicing": APPROVED_FOR_INVOICING,
        "approved_for_checkout": APPROVED_FOR_CHECKOUT,
        "approved_for_settlement": APPROVED_FOR_SETTLEMENT,
        "yearly_discount_percent": str(DEFAULT_YEARLY_DISCOUNT_PERCENT),
        "plans": proposals,
    }
