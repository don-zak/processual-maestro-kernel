from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from processual_api.billing.maestro_units import MAESTRO_UNIT_METRIC

PLAN_FULFILLMENT_CATALOG_VERSION: Final = "2026-08-plan-fulfillment-v2"
QUOTA_METRIC_CODE: Final = MAESTRO_UNIT_METRIC


@dataclass(frozen=True, slots=True)
class PlanFulfillmentSpec:
    plan_code: str
    monthly_unit_allowance: int
    entitlement_codes: tuple[str, ...]
    seat_based_consumption: bool = False

    def __post_init__(self) -> None:
        if not self.plan_code.strip():
            raise ValueError("plan_code must not be blank")
        if self.monthly_unit_allowance <= 0:
            raise ValueError("monthly_unit_allowance must be positive")
        if not self.entitlement_codes:
            raise ValueError("entitlement_codes must not be empty")
        if self.seat_based_consumption:
            raise ValueError("Maestro consumption must be quota based, not seat based")


_PLAN_SPECS = {
    "academic": PlanFulfillmentSpec(
        plan_code="academic",
        monthly_unit_allowance=5_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "standard_support", "academic_use"),
    ),
    "starter": PlanFulfillmentSpec(
        plan_code="starter",
        monthly_unit_allowance=10_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "standard_support"),
    ),
    "enterprise_integration_starter": PlanFulfillmentSpec(
        plan_code="enterprise_integration_starter",
        monthly_unit_allowance=50_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "business_support", "advanced_integration", "enterprise_governance"),
    ),
    "business": PlanFulfillmentSpec(
        plan_code="business",
        monthly_unit_allowance=100_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "business_support"),
    ),
    "enterprise_pilot": PlanFulfillmentSpec(
        plan_code="enterprise_pilot",
        monthly_unit_allowance=500_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "business_support", "enterprise_governance"),
    ),
    "enterprise_core": PlanFulfillmentSpec(
        plan_code="enterprise_core",
        monthly_unit_allowance=1_500_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "business_support", "enterprise_governance"),
    ),
    "enterprise_scale": PlanFulfillmentSpec(
        plan_code="enterprise_scale",
        monthly_unit_allowance=3_000_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "business_support", "enterprise_governance", "advanced_integration"),
    ),
    "enterprise_strategic": PlanFulfillmentSpec(
        plan_code="enterprise_strategic",
        monthly_unit_allowance=5_000_000,
        entitlement_codes=("maestro_execution", "byok_provider_connection", "business_support", "enterprise_governance", "advanced_integration"),
    ),
}

PLAN_FULFILLMENT_SPECS: Final = MappingProxyType(_PLAN_SPECS)
PLAN_CODE_ALIASES: Final = MappingProxyType({
    "pilot_starter": "starter",
    "enterprise": "enterprise_pilot",
    "enterprise_integration": "enterprise_pilot",
})


def normalize_plan_code(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    return PLAN_CODE_ALIASES.get(normalized, normalized)


def get_plan_fulfillment_spec(plan_code: str | None) -> PlanFulfillmentSpec:
    normalized = normalize_plan_code(plan_code)
    try:
        return PLAN_FULFILLMENT_SPECS[normalized]
    except KeyError as exc:
        raise KeyError(f"unknown authoritative plan: {normalized or '(blank)'}") from exc


def monthly_unit_allowance(plan_code: str | None) -> int:
    try:
        return get_plan_fulfillment_spec(plan_code).monthly_unit_allowance
    except KeyError:
        return 0


__all__ = [
    "PLAN_CODE_ALIASES",
    "PLAN_FULFILLMENT_CATALOG_VERSION",
    "PLAN_FULFILLMENT_SPECS",
    "QUOTA_METRIC_CODE",
    "PlanFulfillmentSpec",
    "get_plan_fulfillment_spec",
    "monthly_unit_allowance",
    "normalize_plan_code",
]
