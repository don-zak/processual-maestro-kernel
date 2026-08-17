"""Public pricing-catalog compatibility projection.

The endpoint contract remains intentionally draft and non-publishing. Commercial
plan allowances and entitlements are projected from canonical commercial
contracts, while legacy identifiers are retained only as compatibility aliases.
Selected prices remain private to the canonical commercial pricebook until a
separate publication gate approves exposing them here.
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

SUBSCRIPTION_CATALOG_VERSION: Final = "2026-07-subscriptions-draft-v1"
SUBSCRIPTION_PRICING_STATUS: Final = "draft"
BILLING_POLICY: Final = "byok" if BYOK_ONLY else "provider_managed"
PROVIDER_COST_INCLUDED: Final = (
    maestro_group1_selected_pricing.PROVIDER_COST_INCLUDED
)
PROVIDER_COST_NOTE: Final = (
    "Provider costs are not included. Clients bring their own provider/API key."
)
PRICE_LABEL: Final = "TBD"

# This is presentation/compatibility metadata, not commercial pricing authority.
# Every commercial legacy identifier points at a canonical plan contract.
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
        "display_name": "Enterprise Integration Starter",
        "description": "Starter plan for enterprise integration evaluation.",
        "audience": "enterprise_integration_teams",
        "commercially_listed": True,
    },
    {
        "plan_id": "enterprise",
        "canonical_plan_id": PLAN_CODE_ALIASES["enterprise"],
        "display_name": "Enterprise",
        "description": "Compatibility alias for the canonical Enterprise Pilot plan.",
        "audience": "enterprises",
        "commercially_listed": True,
    },
    {
        "plan_id": "enterprise_integration",
        "canonical_plan_id": PLAN_CODE_ALIASES["enterprise_integration"],
        "display_name": "Enterprise Integration",
        "description": "Compatibility alias reserved for approved enterprise rollout.",
        "audience": "approved_enterprise_integrations",
        "commercially_listed": False,
    },
)


def _canonical_contracts_by_plan() -> dict[str, Any]:
    return {
        contract.plan_code: contract
        for contract in build_catalog_plan_contracts()
    }


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
        # Internal-only compatibility plans are operational, not commercial plans.
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
    """Return the legacy-shaped public view backed by canonical commercial data."""

    contracts_by_plan = _canonical_contracts_by_plan()
    plans = [
        _plan_payload(definition, contracts_by_plan=contracts_by_plan)
        for definition in _COMPATIBILITY_PLAN_DEFINITIONS
    ]
    if not include_unlisted:
        plans = [plan for plan in plans if plan["commercially_listed"]]
    return deepcopy(plans)


def get_subscription_plan(plan_id: str) -> dict[str, Any] | None:
    """Return a compatibility plan by its public legacy identifier."""

    normalized_plan_id = str(plan_id or "").strip().lower()
    for plan in list_subscription_plans(include_unlisted=True):
        if plan["plan_id"] == normalized_plan_id:
            return deepcopy(plan)
    return None


def public_subscription_catalog() -> dict[str, Any]:
    """Return the established draft API contract without publishing prices."""

    plans = list_subscription_plans(include_unlisted=True)
    return {
        "catalog_version": SUBSCRIPTION_CATALOG_VERSION,
        "pricing_version": usage_pricing.PRICING_VERSION,
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": any(plan["checkout_enabled"] for plan in plans),
        "plans": plans,
    }
