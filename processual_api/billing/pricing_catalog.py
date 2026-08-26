"""Public pricing-catalog compatibility projection.

Historical compatibility identifiers remain available to internal lookup helpers,
but the public endpoint is projected only from the current public commercial
journey. This prevents retired enterprise tier aliases from reappearing on the
legacy /pricing surface.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Final

from processual_api.billing import maestro_group1_selected_pricing, usage_pricing
from processual_api.billing.commercial_catalog_contracts import (
    BYOK_ONLY,
    build_catalog_plan_contracts,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_CODE_ALIASES
from processual_api.billing.public_plan_journey import public_plan_journey_catalog

SUBSCRIPTION_CATALOG_VERSION: Final = "2026-08-subscriptions-public-v2"
SUBSCRIPTION_PRICING_STATUS: Final = "draft"
BILLING_POLICY: Final = "byok" if BYOK_ONLY else "provider_managed"
PROVIDER_COST_INCLUDED: Final = maestro_group1_selected_pricing.PROVIDER_COST_INCLUDED
PROVIDER_COST_NOTE: Final = (
    "Provider costs are not included. Clients bring their own provider/API key."
)
PRICE_LABEL: Final = "TBD"

# Internal compatibility metadata. Entries here are not the public exposure
# boundary and may be retained only while persisted historical references exist.
_COMPATIBILITY_PLAN_DEFINITIONS: Final[tuple[dict[str, Any], ...]] = (
    {
        "plan_id": "developer",
        "canonical_plan_id": None,
        "display_name": "Developer",
        "description": "Internal developer plan for testing Maestro usage controls.",
        "audience": "internal_development",
        "commercially_listed": False,
        "features": (
            "Usage-unit tracking",
            "Developer validation",
            "BYOK provider connection",
        ),
    },
    {
        "plan_id": "internal",
        "canonical_plan_id": None,
        "display_name": "Internal",
        "description": "Internal operations plan for Maestro readiness work.",
        "audience": "internal_operations",
        "commercially_listed": False,
        "features": (
            "Usage-unit tracking",
            "Operational validation",
            "BYOK provider connection",
        ),
    },
    {
        "plan_id": "pilot_starter",
        "canonical_plan_id": PLAN_CODE_ALIASES["pilot_starter"],
        "display_name": "Pilot Starter",
        "description": "Non-public compatibility alias for controlled onboarding.",
        "audience": "pilot_clients",
        "commercially_listed": False,
    },
    {
        "plan_id": "starter",
        "canonical_plan_id": "starter",
        "display_name": "Starter",
        "description": "Entry plan for early Maestro usage.",
        "audience": "individuals_and_small_teams",
        "commercially_listed": True,
    },
    {
        "plan_id": "business",
        "canonical_plan_id": "business",
        "display_name": "Business",
        "description": "Business plan for teams needing higher Maestro usage capacity.",
        "audience": "business_teams",
        "commercially_listed": True,
    },
    {
        "plan_id": "enterprise_integration_starter",
        "canonical_plan_id": "enterprise_integration_starter",
        "display_name": "Enterprise Integration Trial",
        "description": "Internal compatibility source for the requirements-based integration trial.",
        "audience": "enterprise_integration_teams",
        "commercially_listed": False,
    },
    {
        "plan_id": "enterprise",
        "canonical_plan_id": PLAN_CODE_ALIASES["enterprise"],
        "display_name": "Enterprise Legacy Alias",
        "description": "Historical compatibility alias retained for stored references only.",
        "audience": "historical_enterprise",
        "commercially_listed": False,
    },
    {
        "plan_id": "enterprise_integration",
        "canonical_plan_id": PLAN_CODE_ALIASES["enterprise_integration"],
        "display_name": "Enterprise Integration Legacy Alias",
        "description": "Historical compatibility alias retained for stored references only.",
        "audience": "historical_enterprise_integrations",
        "commercially_listed": False,
    },
)


def _canonical_contracts_by_plan() -> dict[str, Any]:
    return {contract.plan_code: contract for contract in build_catalog_plan_contracts()}


def _plan_payload(
    plan_definition: dict[str, Any],
    *,
    contracts_by_plan: dict[str, Any],
) -> dict[str, Any]:
    plan_id = str(plan_definition["plan_id"])
    canonical_plan_id = plan_definition.get("canonical_plan_id")
    contract = (
        contracts_by_plan.get(str(canonical_plan_id))
        if canonical_plan_id is not None
        else None
    )

    if canonical_plan_id is not None and contract is None:
        raise ValueError(
            f"Compatibility plan points at unknown canonical plan: {canonical_plan_id}"
        )

    if contract is not None:
        allowance = contract.included_maestro_units
        features = [item.value for item in contract.entitlements]
    else:
        allowance = usage_pricing.monthly_unit_allowance(plan_id)
        features = list(plan_definition["features"])

    if allowance <= 0:
        raise ValueError(f"Unknown monthly unit allowance for compatibility plan: {plan_id}")

    return {
        "plan_id": plan_id,
        "display_name": plan_definition["display_name"],
        "description": plan_definition["description"],
        "audience": plan_definition["audience"],
        "commercially_listed": bool(plan_definition["commercially_listed"]),
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "price_label": PRICE_LABEL,
        "monthly_price_usd": None,
        "yearly_price_usd": None,
        "monthly_unit_allowance": allowance,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": False,
        "lemon_variant_key_monthly": None,
        "lemon_variant_key_yearly": None,
        "features": features,
    }


def list_subscription_plans(*, include_unlisted: bool = True) -> list[dict[str, Any]]:
    """Return internal compatibility plans for historical consumers."""

    contracts_by_plan = _canonical_contracts_by_plan()
    plans = [
        _plan_payload(definition, contracts_by_plan=contracts_by_plan)
        for definition in _COMPATIBILITY_PLAN_DEFINITIONS
    ]
    if not include_unlisted:
        plans = [plan for plan in plans if plan["commercially_listed"]]
    return deepcopy(plans)


def get_subscription_plan(plan_id: str) -> dict[str, Any] | None:
    """Return an internal compatibility plan by legacy identifier."""

    normalized_plan_id = str(plan_id or "").strip().lower()
    for plan in list_subscription_plans(include_unlisted=True):
        if plan["plan_id"] == normalized_plan_id:
            return deepcopy(plan)
    return None


def _public_plan_projection() -> list[dict[str, Any]]:
    current = public_plan_journey_catalog()["plans"]
    projected: list[dict[str, Any]] = []
    for plan in current:
        monthly_price = plan.get("monthly_price_usd")
        if monthly_price is not None:
            price_label = f"USD {monthly_price} / month"
        elif plan.get("commercial_model") == "requirements_based_evaluation":
            price_label = "Evaluation quote after assessment"
        elif plan.get("commercial_model") == "requirements_based_contract":
            price_label = "Enterprise proposal after requirements review"
        else:
            price_label = "Pricing after assessment"

        projected.append(
            {
                "plan_id": plan["plan_id"],
                "display_name": plan["display_name"],
                "description": plan["description"],
                "audience": plan["audience"],
                "commercially_listed": True,
                "pricing_status": SUBSCRIPTION_PRICING_STATUS,
                "price_label": price_label,
                "monthly_price_usd": monthly_price,
                "yearly_price_usd": plan.get("annual_price_usd"),
                "monthly_unit_allowance": plan.get("included_quota_units"),
                "billing_policy": BILLING_POLICY,
                "provider_cost_included": PROVIDER_COST_INCLUDED,
                "provider_cost_note": PROVIDER_COST_NOTE,
                "checkout_enabled": False,
                "lemon_variant_key_monthly": None,
                "lemon_variant_key_yearly": None,
                "features": list(plan.get("features") or []),
                "requires_assessment": bool(plan.get("requires_assessment")),
                "commercial_model": plan.get("commercial_model"),
            }
        )
    return projected


def public_subscription_catalog() -> dict[str, Any]:
    """Return only the current public commercial plan projection."""

    plans = _public_plan_projection()
    return {
        "catalog_version": SUBSCRIPTION_CATALOG_VERSION,
        "pricing_version": usage_pricing.PRICING_VERSION,
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": False,
        "plans": deepcopy(plans),
    }
