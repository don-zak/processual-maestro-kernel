from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final

PRICING_VERSION: Final = "2026-07-byok-v1"
BILLING_POLICY: Final = "byok"
BILLING_SCOPE: Final = "maestro_usage_units"
PROVIDER_COST_INCLUDED: Final = False

DEVELOPER_UNIT_ALLOWANCE: Final = 2_000
STARTER_UNIT_ALLOWANCE: Final = 10_000
BUSINESS_UNIT_ALLOWANCE: Final = 100_000
ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE: Final = 50_000
ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE: Final = 500_000

PLAN_MONTHLY_UNIT_ALLOWANCES: Final[dict[str, int]] = {
    "developer": DEVELOPER_UNIT_ALLOWANCE,
    "internal": DEVELOPER_UNIT_ALLOWANCE,
    "starter": STARTER_UNIT_ALLOWANCE,
    "pilot_starter": STARTER_UNIT_ALLOWANCE,
    "business": BUSINESS_UNIT_ALLOWANCE,
    "enterprise_integration_starter": (
        ENTERPRISE_INTEGRATION_STARTER_UNIT_ALLOWANCE
    ),
    "enterprise": ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE,
    "enterprise_integration": ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE,
}

ENTERPRISE_INTEGRATION_PLANS: Final[frozenset[str]] = frozenset(
    {
        "enterprise",
        "enterprise_integration",
        "enterprise_integration_starter",
        "enterprise_custom",
    }
)

FREE_OPERATIONAL_ENDPOINTS: Final[frozenset[str]] = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/adapters/status",
        "/cgt/govern/status",
        "/settings/subscription",
    }
)

FIXED_ENDPOINT_UNIT_COSTS: Final[dict[str, int]] = {
    "/cgt/analyze": 1,
    "/cgt/govern": 1,
    "/cgt/govern/compare": 2,
    "/cgt/govern/report": 3,
    "/reports/fate": 2,
    "/reports/generate-llm": 5,
    "/cgt/govern/auto-repair": 5,
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
    path = str(endpoint or "/").split("?", 1)[0].strip() or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return path


def normalize_plan_id(plan_id: str | None) -> str:
    return str(plan_id or "").strip().lower().replace(" ", "_")


def monthly_unit_allowance(plan_id: str | None) -> int:
    return PLAN_MONTHLY_UNIT_ALLOWANCES.get(normalize_plan_id(plan_id), 0)


def allows_enterprise_integration(plan_id: str | None) -> bool:
    return normalize_plan_id(plan_id) in ENTERPRISE_INTEGRATION_PLANS


def endpoint_class(endpoint: str) -> str:
    path = normalize_endpoint(endpoint)

    if path in FREE_OPERATIONAL_ENDPOINTS:
        return "free_operational_check"
    if path == "/cgt/govern/batch":
        return "batch_governance_evaluation"
    if path.startswith("/reports/"):
        return "report_generation"
    if path.startswith("/cgt/govern"):
        return "governance_evaluation"
    if path.startswith("/cgt/analyze"):
        return "analysis_evaluation"

    return "metered_api_request"


def units_for_endpoint(endpoint: str, item_count: int | None = None) -> int:
    path = normalize_endpoint(endpoint)

    if path in FREE_OPERATIONAL_ENDPOINTS:
        return 0

    if path == "/cgt/govern/batch":
        return max(int(item_count or 1), 1)

    return FIXED_ENDPOINT_UNIT_COSTS.get(path, 1)


def pricing_decision(endpoint: str, item_count: int | None = None) -> PricingDecision:
    path = normalize_endpoint(endpoint)

    return PricingDecision(
        endpoint=path,
        endpoint_class=endpoint_class(path),
        units_charged=units_for_endpoint(path, item_count=item_count),
    )
