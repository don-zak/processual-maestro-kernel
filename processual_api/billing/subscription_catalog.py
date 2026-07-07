"""Draft subscription catalog for Processual Maestro.

This module is intentionally public-safe. It does not expose Lemon Squeezy
variant IDs, provider secrets, API credentials, or production-ready prices.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from processual_api.billing.usage_pricing import (
    BILLING_POLICY,
    PRICING_VERSION,
    PROVIDER_COST_INCLUDED,
    monthly_unit_allowance,
)

SUBSCRIPTION_CATALOG_VERSION = "2026-07-subscriptions-draft-v1"
SUBSCRIPTION_PRICING_STATUS = "draft"

PROVIDER_COST_NOTE = (
    "Provider costs are not included. Clients bring their own provider/API key."
)

_DRAFT_PRICE_LABEL = "TBD"

_PLAN_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "plan_id": "developer",
        "display_name": "Developer",
        "description": "Internal developer plan for testing Maestro usage controls.",
        "audience": "internal_development",
        "commercially_listed": False,
        "features": [
            "Usage-unit tracking",
            "Developer validation",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "internal",
        "display_name": "Internal",
        "description": "Internal operations plan for Maestro readiness work.",
        "audience": "internal_operations",
        "commercially_listed": False,
        "features": [
            "Usage-unit tracking",
            "Operational validation",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "pilot_starter",
        "display_name": "Pilot Starter",
        "description": "Non-public pilot plan for early controlled onboarding.",
        "audience": "pilot_clients",
        "commercially_listed": False,
        "features": [
            "Pilot usage-unit tracking",
            "Client usage summary",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "starter",
        "display_name": "Starter",
        "description": "Entry plan for early Maestro usage.",
        "audience": "individuals_and_small_teams",
        "commercially_listed": True,
        "features": [
            "Maestro usage-unit tracking",
            "Client usage summary",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "business",
        "display_name": "Business",
        "description": "Business plan for teams needing higher Maestro usage capacity.",
        "audience": "business_teams",
        "commercially_listed": True,
        "features": [
            "Higher monthly Maestro unit allowance",
            "Client usage summary",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "enterprise_integration_starter",
        "display_name": "Enterprise Integration Starter",
        "description": "Starter plan for enterprise integration evaluation.",
        "audience": "enterprise_integration_teams",
        "commercially_listed": True,
        "features": [
            "Enterprise integration readiness",
            "Usage-unit tracking",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "enterprise",
        "display_name": "Enterprise",
        "description": "Enterprise plan for larger supervised Maestro deployments.",
        "audience": "enterprises",
        "commercially_listed": True,
        "features": [
            "Enterprise Maestro usage capacity",
            "Supervised deployment support",
            "BYOK provider connection",
        ],
    },
    {
        "plan_id": "enterprise_integration",
        "display_name": "Enterprise Integration",
        "description": "Advanced enterprise integration plan reserved for approved rollout.",
        "audience": "approved_enterprise_integrations",
        "commercially_listed": False,
        "features": [
            "Advanced enterprise integration readiness",
            "Usage-unit tracking",
            "BYOK provider connection",
        ],
    },
)


def _plan_payload(plan_definition: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(plan_definition["plan_id"])
    allowance = monthly_unit_allowance(plan_id)

    if allowance is None:
        raise ValueError(f"Unknown monthly unit allowance for subscription plan: {plan_id}")

    return {
        "plan_id": plan_id,
        "display_name": plan_definition["display_name"],
        "description": plan_definition["description"],
        "audience": plan_definition["audience"],
        "commercially_listed": bool(plan_definition["commercially_listed"]),
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "price_label": _DRAFT_PRICE_LABEL,
        "monthly_price_usd": None,
        "yearly_price_usd": None,
        "monthly_unit_allowance": allowance,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": False,
        "lemon_variant_key_monthly": None,
        "lemon_variant_key_yearly": None,
        "features": list(plan_definition["features"]),
    }


def list_subscription_plans(*, include_unlisted: bool = True) -> list[dict[str, Any]]:
    """Return draft subscription plans resolved from the usage-pricing catalog."""

    plans = [_plan_payload(plan_definition) for plan_definition in _PLAN_DEFINITIONS]
    if not include_unlisted:
        plans = [plan for plan in plans if plan["commercially_listed"]]
    return deepcopy(plans)


def get_subscription_plan(plan_id: str) -> dict[str, Any] | None:
    """Return a single subscription plan by ID, or None when it is unknown."""

    normalized_plan_id = str(plan_id or "").strip()
    for plan in list_subscription_plans(include_unlisted=True):
        if plan["plan_id"] == normalized_plan_id:
            return deepcopy(plan)
    return None


def public_subscription_catalog() -> dict[str, Any]:
    """Return the public-safe draft subscription catalog payload."""

    plans = list_subscription_plans(include_unlisted=True)
    return {
        "catalog_version": SUBSCRIPTION_CATALOG_VERSION,
        "pricing_version": PRICING_VERSION,
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": any(plan["checkout_enabled"] for plan in plans),
        "plans": plans,
    }
