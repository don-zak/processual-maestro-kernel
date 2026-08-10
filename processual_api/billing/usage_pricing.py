from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final

from processual_api.billing.maestro_units import (
    MAESTRO_UNIT_METRIC,
    MAESTRO_UNIT_RULES,
    maestro_endpoint_class,
    maestro_units_for_endpoint,
    normalize_maestro_endpoint,
)
from processual_api.billing.plan_capability_matrix import plan_can_execute
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_SPECS,
    normalize_plan_code,
)

PRICING_VERSION: Final = "2026-08-maestro-units-v1"
BILLING_POLICY: Final = "byok"
BILLING_SCOPE: Final = MAESTRO_UNIT_METRIC
PROVIDER_COST_INCLUDED: Final = False

DEVELOPER_UNIT_ALLOWANCE: Final = 2_000
STARTER_UNIT_ALLOWANCE: Final = PLAN_FULFILLMENT_SPECS["starter"].monthly_unit_allowance
BUSINESS_UNIT_ALLOWANCE: Final = PLAN_FULFILLMENT_SPECS["business"].monthly_unit_allowance
ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE: Final = PLAN_FULFILLMENT_SPECS[
    "enterprise_integration_starter"
].monthly_unit_allowance
ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE: Final = PLAN_FULFILLMENT_SPECS[
    "enterprise_pilot"
].monthly_unit_allowance

PLAN_MONTHLY_UNIT_ALLOWANCES: Final[dict[str, int]] = {
    "developer": DEVELOPER_UNIT_ALLOWANCE,
    "internal": DEVELOPER_UNIT_ALLOWANCE,
    **{code: spec.monthly_unit_allowance for code, spec in PLAN_FULFILLMENT_SPECS.items()},
    "pilot_starter": STARTER_UNIT_ALLOWANCE,
    "enterprise": ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE,
    "enterprise_integration": ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE,
}

LEGACY_ENTERPRISE_INTEGRATION_PLANS: Final[frozenset[str]] = frozenset({"enterprise_private"})
FREE_OPERATIONAL_ENDPOINTS: Final[frozenset[str]] = frozenset(
    path for path, rule in MAESTRO_UNIT_RULES.items() if rule.free
)
FIXED_ENDPOINT_UNIT_COSTS: Final[dict[str, int]] = {
    path: rule.units
    for path, rule in MAESTRO_UNIT_RULES.items()
    if not rule.free and not rule.variable_by_item_count
}


@dataclass(frozen=True, slots=True)
class PricingDecision:
    endpoint: str
    endpoint_class: str
    units_charged: int
    pricing_version: str = PRICING_VERSION
    billing_policy: str = BILLING_POLICY
    billing_scope: str = BILLING_SCOPE
    provider_cost_included: bool = PROVIDER_COST_INCLUDED

    def to_usage_record(self) -> dict[str, Any]:
        return asdict(self)


def normalize_endpoint(endpoint: str) -> str:
    return normalize_maestro_endpoint(endpoint)


def normalize_plan_id(plan_id: str | None) -> str:
    return str(plan_id or "").strip().lower().replace(" ", "_")


def canonical_plan_id(plan_id: str | None) -> str:
    return normalize_plan_code(plan_id)


def monthly_unit_allowance(plan_id: str | None) -> int:
    normalized = normalize_plan_id(plan_id)
    if normalized in PLAN_MONTHLY_UNIT_ALLOWANCES:
        return PLAN_MONTHLY_UNIT_ALLOWANCES[normalized]
    return PLAN_MONTHLY_UNIT_ALLOWANCES.get(canonical_plan_id(plan_id), 0)


def allows_enterprise_integration(plan_id: str | None) -> bool:
    normalized = normalize_plan_id(plan_id)
    if normalized in LEGACY_ENTERPRISE_INTEGRATION_PLANS:
        return True
    return plan_can_execute(plan_id, "advanced_integration")


def enterprise_integration_capability(plan_id: str | None) -> dict[str, Any]:
    normalized_plan_id = normalize_plan_id(plan_id)
    canonical = canonical_plan_id(plan_id)
    legacy = normalized_plan_id in LEGACY_ENTERPRISE_INTEGRATION_PLANS
    enabled = allows_enterprise_integration(plan_id)
    eligible = [
        code
        for code in PLAN_FULFILLMENT_SPECS
        if plan_can_execute(code, "advanced_integration")
    ]
    return {
        "enabled": enabled,
        "status": "available" if enabled else "locked",
        "plan_id": normalized_plan_id or "unknown",
        "normalized_plan_id": normalized_plan_id or "unknown",
        "canonical_plan_id": canonical or normalized_plan_id or "unknown",
        "legacy_compatibility": legacy,
        "eligible_plans": sorted(eligible),
    }


def endpoint_class(endpoint: str) -> str:
    return maestro_endpoint_class(endpoint)


def units_for_endpoint(endpoint: str, item_count: int | None = None) -> int:
    return maestro_units_for_endpoint(endpoint, item_count=item_count)


def pricing_decision(endpoint: str, item_count: int | None = None) -> PricingDecision:
    path = normalize_endpoint(endpoint)
    return PricingDecision(
        endpoint=path,
        endpoint_class=endpoint_class(path),
        units_charged=units_for_endpoint(path, item_count=item_count),
    )
