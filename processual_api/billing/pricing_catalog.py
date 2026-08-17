"""Compatibility pricing catalog derived from canonical commercial contracts.

This module preserves the public ``/billing/pricing-catalog`` payload shape while
moving plan identity, quotas, and selected USD prices onto the canonical
commercial catalog authority. It does not publish offers or enable checkout.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from processual_api.billing.commercial_catalog_contracts import (
    CATALOG_CONTRACT_VERSION,
    CATALOG_STATUS,
    OfferVisibility,
    build_catalog_plan_contracts,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    SELECTED_PROPOSAL_VERSION,
)
from processual_api.billing.usage_pricing import BILLING_POLICY

SUBSCRIPTION_CATALOG_VERSION = CATALOG_CONTRACT_VERSION
SUBSCRIPTION_PRICING_STATUS = CATALOG_STATUS
PROVIDER_COST_INCLUDED = False
PROVIDER_COST_NOTE = (
    "Provider costs are not included. Clients bring their own provider/API key."
)
PRICE_LABEL = "Selected pricing — publication approval required"


def _display_name(plan_code: str) -> str:
    return plan_code.replace("_", " ").title()


def _plan_payload(contract: Any) -> dict[str, Any]:
    display_name = _display_name(contract.plan_code)
    return {
        "plan_id": contract.plan_code,
        "display_name": display_name,
        "description": (
            f"Canonical commercial plan for {display_name}; publication approval "
            "is still required."
        ),
        "audience": contract.audience.value,
        "commercially_listed": (
            contract.visibility is OfferVisibility.PUBLIC_CANDIDATE
        ),
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "price_label": PRICE_LABEL,
        "monthly_price_usd": str(contract.monthly_price_usd),
        "yearly_price_usd": str(contract.annual_price_usd),
        "monthly_unit_allowance": contract.included_maestro_units,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": False,
        "lemon_variant_key_monthly": None,
        "lemon_variant_key_yearly": None,
        "features": [item.value for item in contract.entitlements],
    }


def list_subscription_plans(*, include_unlisted: bool = True) -> list[dict[str, Any]]:
    """Return compatibility plans projected from canonical contracts."""

    plans = [_plan_payload(contract) for contract in build_catalog_plan_contracts()]
    if not include_unlisted:
        plans = [plan for plan in plans if plan["commercially_listed"]]
    return deepcopy(plans)


def get_subscription_plan(plan_id: str) -> dict[str, Any] | None:
    """Return one canonical compatibility plan by ID."""

    normalized_plan_id = str(plan_id or "").strip().lower()
    for plan in list_subscription_plans(include_unlisted=True):
        if plan["plan_id"] == normalized_plan_id:
            return deepcopy(plan)
    return None


def public_subscription_catalog() -> dict[str, Any]:
    """Return the public-safe compatibility catalog without activation."""

    plans = list_subscription_plans(include_unlisted=True)
    return {
        "catalog_version": SUBSCRIPTION_CATALOG_VERSION,
        "pricing_version": SELECTED_PROPOSAL_VERSION,
        "pricing_status": SUBSCRIPTION_PRICING_STATUS,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": PROVIDER_COST_NOTE,
        "checkout_enabled": any(plan["checkout_enabled"] for plan in plans),
        "plans": plans,
    }
