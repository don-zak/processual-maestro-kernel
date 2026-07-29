"""Integrated Maestro Group 1 pricing review engine.

Consolidated flow:
measurement evidence -> Maestro usage units -> internal cost factor
-> commercial value factor -> quota simulation -> price review.

This module never approves pricing, checkout, invoicing, settlement, or quota
enforcement. LLM provider cost is excluded because the platform is BYOK-only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Final

from processual_api.billing.maestro_calibration_contracts import (
    CalibrationQuantities,
    MaestroResourceBand,
)
from processual_api.billing.usage_pricing import (
    BUSINESS_UNIT_ALLOWANCE,
    ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE,
    STARTER_UNIT_ALLOWANCE,
)

GROUP1_PRICING_REVIEW_VERSION: Final = "2026-07-group1-pricing-review-v2"
PRICING_STATUS: Final = "draft_review"
CURRENCY: Final = "USD"

SHADOW_ONLY: Final = True
BYOK_ONLY: Final = True
PROVIDER_COST_INCLUDED: Final = False
COMMERCIAL_ENFORCEMENT_ENABLED: Final = False
APPROVED_FOR_QUOTA: Final = False
APPROVED_FOR_PRICING: Final = False
APPROVED_FOR_INVOICING: Final = False
APPROVED_FOR_CHECKOUT: Final = False
APPROVED_FOR_SETTLEMENT: Final = False

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
CENT = Decimal("0.01")
UNIT_PRECISION = Decimal("0.0001")
RATE_PRECISION = Decimal("0.000001")

MAESTRO_UNIT_WEIGHTS: Final[dict[str, Decimal]] = {
    "base_executions": Decimal("1.00"),
    "integration_actions": Decimal("0.25"),
    "equivalent_pages": Decimal("0.04"),
    "records_processed": Decimal("0.001"),
    "verification_items": Decimal("0.04"),
    "standard_supervision_gates": Decimal("2.00"),
    "extended_supervision_gates": Decimal("5.00"),
    "excess_storage_gb_month": Decimal("1.00"),
}

RESOURCE_BAND_MULTIPLIERS: Final[dict[MaestroResourceBand, Decimal | None]] = {
    MaestroResourceBand.NORMAL: Decimal("1.00"),
    MaestroResourceBand.HEAVY: Decimal("1.25"),
    MaestroResourceBand.EXTREME: Decimal("1.50"),
    MaestroResourceBand.CUSTOM: None,
}


class PricingReviewValidationError(ValueError):
    """Raised when Group 1 pricing review inputs violate an invariant."""


class PricingScenarioName(StrEnum):
    CONSERVATIVE = "conservative"
    RECOMMENDED = "recommended"
    RESILIENT = "resilient"


class CommercialValueBand(StrEnum):
    STANDARD = "standard"
    ADVANCED = "advanced"
    ACADEMIC_RESEARCH = "academic_research"
    ENTERPRISE_GOVERNED = "enterprise_governed"
    CUSTOM = "custom"


COMMERCIAL_VALUE_MULTIPLIERS: Final[dict[CommercialValueBand, Decimal | None]] = {
    CommercialValueBand.STANDARD: Decimal("1.00"),
    CommercialValueBand.ADVANCED: Decimal("1.08"),
    CommercialValueBand.ACADEMIC_RESEARCH: Decimal("1.12"),
    CommercialValueBand.ENTERPRISE_GOVERNED: Decimal("1.18"),
    CommercialValueBand.CUSTOM: None,
}


@dataclass(frozen=True, slots=True)
class MaestroUnitResult:
    raw_units: Decimal
    settled_units: Decimal | None
    resource_band: MaestroResourceBand
    manual_review_required: bool

    def __post_init__(self) -> None:
        _require_non_negative_decimal("raw_units", self.raw_units)
        if self.settled_units is not None:
            _require_non_negative_decimal("settled_units", self.settled_units)
        if not isinstance(self.resource_band, MaestroResourceBand):
            raise PricingReviewValidationError("resource_band must be MaestroResourceBand")
        if not isinstance(self.manual_review_required, bool):
            raise PricingReviewValidationError("manual_review_required must be bool")
        if self.resource_band is MaestroResourceBand.CUSTOM:
            if self.settled_units is not None:
                raise PricingReviewValidationError("custom workloads must not auto-settle")
            if not self.manual_review_required:
                raise PricingReviewValidationError("custom workloads must require manual review")


@dataclass(frozen=True, slots=True)
class UnitCostScenario:
    name: PricingScenarioName
    infrastructure_cost_per_unit: Decimal
    operations_cost_per_unit: Decimal
    support_cost_per_unit: Decimal
    fixed_cost_allocation_per_unit: Decimal
    retry_failure_overhead_percent: Decimal
    risk_reserve_percent: Decimal
    processor_percent: Decimal
    tax_reserve_percent: Decimal
    target_net_margin_percent: Decimal
    uniqueness_premium_percent: Decimal
    processor_fixed_fee: Decimal = Decimal("0.50")

    def __post_init__(self) -> None:
        if not isinstance(self.name, PricingScenarioName):
            raise PricingReviewValidationError("name must be PricingScenarioName")
        for field_name in (
            "infrastructure_cost_per_unit",
            "operations_cost_per_unit",
            "support_cost_per_unit",
            "fixed_cost_allocation_per_unit",
            "processor_fixed_fee",
        ):
            _require_non_negative_decimal(
                field_name,
                getattr(self, field_name),
            )
        for field_name in (
            "retry_failure_overhead_percent",
            "risk_reserve_percent",
            "processor_percent",
            "tax_reserve_percent",
            "target_net_margin_percent",
            "uniqueness_premium_percent",
        ):
            _require_percentage(field_name, getattr(self, field_name))
        deduction_total = self.processor_percent + self.tax_reserve_percent + self.target_net_margin_percent
        if deduction_total >= HUNDRED:
            raise PricingReviewValidationError("processor, tax reserve, and margin must total less than 100%")

    @property
    def direct_cost_per_unit(self) -> Decimal:
        return (
            self.infrastructure_cost_per_unit
            + self.operations_cost_per_unit
            + self.support_cost_per_unit
            + self.fixed_cost_allocation_per_unit
        )

    @property
    def operationally_adjusted_cost_per_unit(self) -> Decimal:
        multiplier = ONE + (self.retry_failure_overhead_percent / HUNDRED)
        return _rate(self.direct_cost_per_unit * multiplier)

    @property
    def risk_adjusted_cost_per_unit(self) -> Decimal:
        multiplier = ONE + (self.risk_reserve_percent / HUNDRED)
        return _rate(self.operationally_adjusted_cost_per_unit * multiplier)

    @property
    def minimum_sale_price_per_unit(self) -> Decimal:
        retained_share = ONE - (
            (self.processor_percent + self.tax_reserve_percent + self.target_net_margin_percent) / HUNDRED
        )
        return _rate(self.risk_adjusted_cost_per_unit / retained_share)

    @property
    def uniqueness_adjusted_price_per_unit(self) -> Decimal:
        multiplier = ONE + (self.uniqueness_premium_percent / HUNDRED)
        return _rate(self.minimum_sale_price_per_unit * multiplier)


@dataclass(frozen=True, slots=True)
class PlanPricingReview:
    plan_id: str
    monthly_unit_allowance: int
    scenario_name: PricingScenarioName
    value_band: CommercialValueBand
    estimated_monthly_cost: Decimal
    minimum_monthly_price: Decimal
    recommended_monthly_price: Decimal
    recommended_yearly_price: Decimal
    overage_price_per_1000_units: Decimal
    yearly_discount_percent: Decimal
    currency: str = CURRENCY
    price_status: str = PRICING_STATUS
    approved_for_checkout: bool = False

    def __post_init__(self) -> None:
        if not self.plan_id or not self.plan_id.strip():
            raise PricingReviewValidationError("plan_id must not be blank")
        if (
            not isinstance(self.monthly_unit_allowance, int)
            or isinstance(self.monthly_unit_allowance, bool)
            or self.monthly_unit_allowance <= 0
        ):
            raise PricingReviewValidationError("monthly_unit_allowance must be a positive int")
        if not isinstance(self.scenario_name, PricingScenarioName):
            raise PricingReviewValidationError("scenario_name must be PricingScenarioName")
        if not isinstance(self.value_band, CommercialValueBand):
            raise PricingReviewValidationError("value_band must be CommercialValueBand")
        for field_name in (
            "estimated_monthly_cost",
            "minimum_monthly_price",
            "recommended_monthly_price",
            "recommended_yearly_price",
            "overage_price_per_1000_units",
            "yearly_discount_percent",
        ):
            _require_non_negative_decimal(
                field_name,
                getattr(self, field_name),
            )
        if self.price_status != PRICING_STATUS:
            raise PricingReviewValidationError("price_status must remain draft_review")
        if self.approved_for_checkout:
            raise PricingReviewValidationError("checkout must remain disabled during pricing review")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["scenario_name"] = self.scenario_name.value
        payload["value_band"] = self.value_band.value
        for key in (
            "estimated_monthly_cost",
            "minimum_monthly_price",
            "recommended_monthly_price",
            "recommended_yearly_price",
            "overage_price_per_1000_units",
            "yearly_discount_percent",
        ):
            payload[key] = str(payload[key])
        return payload


def _require_non_negative_decimal(
    name: str,
    value: object,
) -> None:
    if not isinstance(value, Decimal):
        raise PricingReviewValidationError(f"{name} must be Decimal")
    try:
        if not value.is_finite():
            raise PricingReviewValidationError(f"{name} must be finite")
    except InvalidOperation as exc:
        raise PricingReviewValidationError(f"{name} must be a valid Decimal") from exc
    if value < ZERO:
        raise PricingReviewValidationError(f"{name} must not be negative")


def _require_percentage(
    name: str,
    value: object,
) -> None:
    _require_non_negative_decimal(name, value)
    if value > HUNDRED:
        raise PricingReviewValidationError(f"{name} must not exceed 100")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _rate(value: Decimal) -> Decimal:
    return value.quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)


REVIEW_SCENARIOS: Final[tuple[UnitCostScenario, ...]] = (
    UnitCostScenario(
        name=PricingScenarioName.CONSERVATIVE,
        infrastructure_cost_per_unit=Decimal("0.00045"),
        operations_cost_per_unit=Decimal("0.00035"),
        support_cost_per_unit=Decimal("0.00025"),
        fixed_cost_allocation_per_unit=Decimal("0.00020"),
        retry_failure_overhead_percent=Decimal("5"),
        risk_reserve_percent=Decimal("6"),
        processor_percent=Decimal("5"),
        tax_reserve_percent=Decimal("8"),
        target_net_margin_percent=Decimal("30"),
        uniqueness_premium_percent=Decimal("0"),
    ),
    UnitCostScenario(
        name=PricingScenarioName.RECOMMENDED,
        infrastructure_cost_per_unit=Decimal("0.00055"),
        operations_cost_per_unit=Decimal("0.00045"),
        support_cost_per_unit=Decimal("0.00035"),
        fixed_cost_allocation_per_unit=Decimal("0.00030"),
        retry_failure_overhead_percent=Decimal("8"),
        risk_reserve_percent=Decimal("8"),
        processor_percent=Decimal("5"),
        tax_reserve_percent=Decimal("10"),
        target_net_margin_percent=Decimal("40"),
        uniqueness_premium_percent=Decimal("10"),
    ),
    UnitCostScenario(
        name=PricingScenarioName.RESILIENT,
        infrastructure_cost_per_unit=Decimal("0.00070"),
        operations_cost_per_unit=Decimal("0.00060"),
        support_cost_per_unit=Decimal("0.00050"),
        fixed_cost_allocation_per_unit=Decimal("0.00040"),
        retry_failure_overhead_percent=Decimal("12"),
        risk_reserve_percent=Decimal("12"),
        processor_percent=Decimal("6"),
        tax_reserve_percent=Decimal("12"),
        target_net_margin_percent=Decimal("50"),
        uniqueness_premium_percent=Decimal("10"),
    ),
)

ENTERPRISE_PILOT_UNIT_ALLOWANCE: Final = 500_000
ENTERPRISE_CORE_UNIT_ALLOWANCE: Final = 1_500_000
ENTERPRISE_SCALE_UNIT_ALLOWANCE: Final = 3_000_000
ENTERPRISE_STRATEGIC_UNIT_ALLOWANCE: Final = 5_000_000

PLAN_REVIEW_CONFIG: Final[dict[str, tuple[int, CommercialValueBand]]] = {
    "academic": (5_000, CommercialValueBand.ACADEMIC_RESEARCH),
    "starter": (STARTER_UNIT_ALLOWANCE, CommercialValueBand.STANDARD),
    "enterprise_integration_starter": (
        ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE,
        CommercialValueBand.ADVANCED,
    ),
    "business": (
        BUSINESS_UNIT_ALLOWANCE,
        CommercialValueBand.ADVANCED,
    ),
    "enterprise_pilot": (
        ENTERPRISE_PILOT_UNIT_ALLOWANCE,
        CommercialValueBand.ENTERPRISE_GOVERNED,
    ),
    "enterprise_core": (
        ENTERPRISE_CORE_UNIT_ALLOWANCE,
        CommercialValueBand.ENTERPRISE_GOVERNED,
    ),
    "enterprise_scale": (
        ENTERPRISE_SCALE_UNIT_ALLOWANCE,
        CommercialValueBand.ENTERPRISE_GOVERNED,
    ),
    "enterprise_strategic": (
        ENTERPRISE_STRATEGIC_UNIT_ALLOWANCE,
        CommercialValueBand.ENTERPRISE_GOVERNED,
    ),
}


def calculate_maestro_units(
    quantities: CalibrationQuantities,
    resource_band: MaestroResourceBand = MaestroResourceBand.NORMAL,
) -> MaestroUnitResult:
    if not isinstance(quantities, CalibrationQuantities):
        raise PricingReviewValidationError("quantities must be CalibrationQuantities")
    if not isinstance(resource_band, MaestroResourceBand):
        raise PricingReviewValidationError("resource_band must be MaestroResourceBand")
    raw_units = ZERO
    for field_name, weight in MAESTRO_UNIT_WEIGHTS.items():
        raw_units += getattr(quantities, field_name) * weight
    raw_units = raw_units.quantize(
        UNIT_PRECISION,
        rounding=ROUND_HALF_UP,
    )
    multiplier = RESOURCE_BAND_MULTIPLIERS[resource_band]
    if multiplier is None:
        return MaestroUnitResult(
            raw_units=raw_units,
            settled_units=None,
            resource_band=resource_band,
            manual_review_required=True,
        )
    settled_units = (raw_units * multiplier).quantize(
        UNIT_PRECISION,
        rounding=ROUND_HALF_UP,
    )
    return MaestroUnitResult(
        raw_units=raw_units,
        settled_units=settled_units,
        resource_band=resource_band,
        manual_review_required=False,
    )


def calculate_plan_pricing(
    plan_id: str,
    monthly_unit_allowance: int,
    scenario: UnitCostScenario,
    value_band: CommercialValueBand,
    *,
    yearly_discount_percent: Decimal = Decimal("15"),
) -> PlanPricingReview:
    if not isinstance(scenario, UnitCostScenario):
        raise PricingReviewValidationError("scenario must be UnitCostScenario")
    if not isinstance(value_band, CommercialValueBand):
        raise PricingReviewValidationError("value_band must be CommercialValueBand")
    _require_percentage(
        "yearly_discount_percent",
        yearly_discount_percent,
    )
    if yearly_discount_percent >= HUNDRED:
        raise PricingReviewValidationError("yearly_discount_percent must be less than 100%")
    if (
        not isinstance(monthly_unit_allowance, int)
        or isinstance(monthly_unit_allowance, bool)
        or monthly_unit_allowance <= 0
    ):
        raise PricingReviewValidationError("monthly_unit_allowance must be a positive int")
    value_multiplier = COMMERCIAL_VALUE_MULTIPLIERS[value_band]
    if value_multiplier is None:
        raise PricingReviewValidationError("custom value bands require manual pricing review")
    units = Decimal(monthly_unit_allowance)
    estimated_monthly_cost = _money(scenario.risk_adjusted_cost_per_unit * units)
    minimum_monthly_price = _money(scenario.minimum_sale_price_per_unit * units + scenario.processor_fixed_fee)
    recommended_unit_price = _rate(scenario.uniqueness_adjusted_price_per_unit * value_multiplier)
    recommended_monthly_price = _money(recommended_unit_price * units + scenario.processor_fixed_fee)
    yearly_multiplier = Decimal("12") * (ONE - yearly_discount_percent / HUNDRED)
    recommended_yearly_price = _money(recommended_monthly_price * yearly_multiplier)
    overage_price_per_1000_units = _money(recommended_unit_price * Decimal("1000") * Decimal("1.15"))
    return PlanPricingReview(
        plan_id=plan_id,
        monthly_unit_allowance=monthly_unit_allowance,
        scenario_name=scenario.name,
        value_band=value_band,
        estimated_monthly_cost=estimated_monthly_cost,
        minimum_monthly_price=minimum_monthly_price,
        recommended_monthly_price=recommended_monthly_price,
        recommended_yearly_price=recommended_yearly_price,
        overage_price_per_1000_units=overage_price_per_1000_units,
        yearly_discount_percent=yearly_discount_percent,
    )


def build_group1_price_review() -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    for scenario in REVIEW_SCENARIOS:
        for plan_id, config in PLAN_REVIEW_CONFIG.items():
            allowance, value_band = config
            plans.append(
                calculate_plan_pricing(
                    plan_id,
                    allowance,
                    scenario,
                    value_band,
                ).to_dict()
            )
    return {
        "review_version": GROUP1_PRICING_REVIEW_VERSION,
        "pricing_status": PRICING_STATUS,
        "currency": CURRENCY,
        "shadow_only": SHADOW_ONLY,
        "byok_only": BYOK_ONLY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "commercial_enforcement_enabled": (COMMERCIAL_ENFORCEMENT_ENABLED),
        "approved_for_quota": APPROVED_FOR_QUOTA,
        "approved_for_pricing": APPROVED_FOR_PRICING,
        "approved_for_invoicing": APPROVED_FOR_INVOICING,
        "approved_for_checkout": APPROVED_FOR_CHECKOUT,
        "approved_for_settlement": APPROVED_FOR_SETTLEMENT,
        "unit_weights": {key: str(value) for key, value in MAESTRO_UNIT_WEIGHTS.items()},
        "value_multipliers": {
            key.value: (str(value) if value is not None else None)
            for key, value in COMMERCIAL_VALUE_MULTIPLIERS.items()
        },
        "scenarios": [
            {
                "name": scenario.name.value,
                "direct_cost_per_unit": str(scenario.direct_cost_per_unit),
                "operationally_adjusted_cost_per_unit": str(scenario.operationally_adjusted_cost_per_unit),
                "risk_adjusted_cost_per_unit": str(scenario.risk_adjusted_cost_per_unit),
                "minimum_sale_price_per_unit": str(scenario.minimum_sale_price_per_unit),
                "uniqueness_adjusted_price_per_unit": str(scenario.uniqueness_adjusted_price_per_unit),
                "retry_failure_overhead_percent": str(scenario.retry_failure_overhead_percent),
                "risk_reserve_percent": str(scenario.risk_reserve_percent),
                "processor_percent": str(scenario.processor_percent),
                "tax_reserve_percent": str(scenario.tax_reserve_percent),
                "target_net_margin_percent": str(scenario.target_net_margin_percent),
                "uniqueness_premium_percent": str(scenario.uniqueness_premium_percent),
            }
            for scenario in REVIEW_SCENARIOS
        ],
        "plans": plans,
    }
