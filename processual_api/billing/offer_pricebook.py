"""Versioned draft offer price book for Processual Maestro.

This module prepares the commercial offer structure without approving prices,
checkout, Lemon variant IDs, or final billing calculations.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from processual_api.billing.subscription_catalog import get_subscription_plan
from processual_api.billing.usage_pricing import (
    BILLING_POLICY,
    PRICING_VERSION,
    PROVIDER_COST_INCLUDED,
    monthly_unit_allowance,
)

OFFER_PRICEBOOK_VERSION = "2026-07-offers-draft-v1"
OFFER_PRICEBOOK_STATUS = "draft_review"
OFFER_PRICE_STATUS = "pending_review"

PRICE_REVIEW_LABEL = "Pricing pending review"
PRICE_CALCULATION_STATUS = "not_defined"

PRICE_REVIEW_NOTE = (
    "No production price is approved yet. Pricing values and calculation method "
    "must be reviewed before checkout can be enabled."
)

_PRICE_INPUTS_PENDING_REVIEW: tuple[str, ...] = (
    "monthly_unit_allowance",
    "billing_interval",
    "support_level",
    "integration_scope",
    "deployment_scope",
    "billing_risk_review",
)

_OFFER_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "offer_id": "starter_trial",
        "plan_id": "starter",
        "display_name": "Starter Trial",
        "billing_interval": "trial",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": False,
        "description": "Draft trial offer for evaluating Starter access.",
    },
    {
        "offer_id": "starter_monthly",
        "plan_id": "starter",
        "display_name": "Starter Monthly",
        "billing_interval": "monthly",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": False,
        "description": "Draft monthly offer for Starter access.",
    },
    {
        "offer_id": "starter_yearly",
        "plan_id": "starter",
        "display_name": "Starter Yearly",
        "billing_interval": "yearly",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": False,
        "description": "Draft yearly offer for Starter access.",
    },
    {
        "offer_id": "business_monthly",
        "plan_id": "business",
        "display_name": "Business Monthly",
        "billing_interval": "monthly",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": False,
        "description": "Draft monthly offer for Business access.",
    },
    {
        "offer_id": "business_yearly",
        "plan_id": "business",
        "display_name": "Business Yearly",
        "billing_interval": "yearly",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": False,
        "description": "Draft yearly offer for Business access.",
    },
    {
        "offer_id": "enterprise_integration_trial",
        "plan_id": "enterprise_integration_starter",
        "display_name": "Enterprise Integration Trial",
        "billing_interval": "trial",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": True,
        "description": "Draft trial offer for enterprise integration evaluation.",
    },
    {
        "offer_id": "enterprise_integration_starter_monthly",
        "plan_id": "enterprise_integration_starter",
        "display_name": "Enterprise Integration Starter Monthly",
        "billing_interval": "monthly",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": True,
        "description": "Draft monthly offer for enterprise integration starter access.",
    },
    {
        "offer_id": "enterprise_integration_starter_yearly",
        "plan_id": "enterprise_integration_starter",
        "display_name": "Enterprise Integration Starter Yearly",
        "billing_interval": "yearly",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": True,
        "description": "Draft yearly offer for enterprise integration starter access.",
    },
    {
        "offer_id": "enterprise_contact",
        "plan_id": "enterprise",
        "display_name": "Enterprise Contact",
        "billing_interval": "contact",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": True,
        "description": "Draft contact-sales offer for supervised enterprise deployments.",
    },
)


_PRICE_FIELDS: tuple[str, ...] = (
    "amount_cents",
    "monthly_amount_cents",
    "yearly_amount_cents",
    "setup_fee_cents",
    "minimum_commit_cents",
    "usage_overage_unit_price_cents",
)


def _offer_payload(offer_definition: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(offer_definition["plan_id"])
    plan = get_subscription_plan(plan_id)
    allowance = monthly_unit_allowance(plan_id)

    if plan is None:
        raise ValueError(f"Unknown subscription plan for offer: {plan_id}")

    if allowance is None:
        raise ValueError(f"Unknown monthly unit allowance for offer plan: {plan_id}")

    payload = {
        "offer_id": offer_definition["offer_id"],
        "plan_id": plan_id,
        "plan_display_name": plan["display_name"],
        "display_name": offer_definition["display_name"],
        "description": offer_definition["description"],
        "billing_interval": offer_definition["billing_interval"],
        "trial_duration_days": offer_definition["trial_duration_days"],
        "commercially_listed": bool(offer_definition["commercially_listed"]),
        "requires_sales_contact": bool(offer_definition["requires_sales_contact"]),
        "pricebook_version": OFFER_PRICEBOOK_VERSION,
        "pricebook_status": OFFER_PRICEBOOK_STATUS,
        "price_status": OFFER_PRICE_STATUS,
        "public_price_label": PRICE_REVIEW_LABEL,
        "price_calculation_status": PRICE_CALCULATION_STATUS,
        "price_review_note": PRICE_REVIEW_NOTE,
        "price_inputs_pending_review": list(_PRICE_INPUTS_PENDING_REVIEW),
        "currency": None,
        "checkout_enabled": False,
        "approval_required_before_checkout": True,
        "monthly_unit_allowance": allowance,
        "allowance_source": "usage_pricing.monthly_unit_allowance",
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "provider_cost_note": plan["provider_cost_note"],
    }

    for price_field in _PRICE_FIELDS:
        payload[price_field] = None

    return payload


def list_offer_prices(*, include_unlisted: bool = True) -> list[dict[str, Any]]:
    """Return draft offers without production prices or checkout enablement."""

    offers = [_offer_payload(offer_definition) for offer_definition in _OFFER_DEFINITIONS]
    if not include_unlisted:
        offers = [offer for offer in offers if offer["commercially_listed"]]
    return deepcopy(offers)


def get_offer_price(offer_id: str) -> dict[str, Any] | None:
    """Return a single draft offer by ID, or None when it is unknown."""

    normalized_offer_id = str(offer_id or "").strip()
    for offer in list_offer_prices(include_unlisted=True):
        if offer["offer_id"] == normalized_offer_id:
            return deepcopy(offer)
    return None


def public_offer_pricebook() -> dict[str, Any]:
    """Return a public-safe draft offer price book payload."""

    offers = list_offer_prices(include_unlisted=False)
    return {
        "pricebook_version": OFFER_PRICEBOOK_VERSION,
        "pricing_version": PRICING_VERSION,
        "pricebook_status": OFFER_PRICEBOOK_STATUS,
        "price_status": OFFER_PRICE_STATUS,
        "public_price_label": PRICE_REVIEW_LABEL,
        "price_calculation_status": PRICE_CALCULATION_STATUS,
        "price_review_note": PRICE_REVIEW_NOTE,
        "currency": None,
        "billing_policy": BILLING_POLICY,
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "checkout_enabled": any(offer["checkout_enabled"] for offer in offers),
        "offers": offers,
    }
