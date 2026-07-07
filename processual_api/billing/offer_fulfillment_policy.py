"""Offer fulfillment policy for pricing and checkout readiness.

This module does not approve prices and does not enable checkout.
It only classifies offers as self-service or enterprise-review.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SELF_SERVICE_POLICY: dict[str, Any] = {
    "fulfillment_mode": "self_service",
    "requires_supervisor_review": False,
    "registration_required": True,
    "payment_required": True,
    "activation_policy": "automatic_after_successful_payment",
    "checkout_mode": "direct_checkout_when_approved",
    "custom_quote_required": False,
}

ENTERPRISE_REVIEW_POLICY: dict[str, Any] = {
    "fulfillment_mode": "enterprise_review",
    "requires_supervisor_review": True,
    "registration_required": True,
    "payment_required": False,
    "activation_policy": "manual_after_enterprise_review",
    "checkout_mode": "contact_sales",
    "custom_quote_required": True,
}


ENTERPRISE_PLAN_IDS = {
    "enterprise",
    "enterprise_integration_starter",
}

ENTERPRISE_OFFER_IDS = {
    "enterprise_contact",
    "enterprise_integration_trial",
    "enterprise_integration_starter_monthly",
    "enterprise_integration_starter_yearly",
}


def classify_offer_fulfillment(offer: dict[str, Any]) -> dict[str, Any]:
    """Return a public-safe fulfillment policy for an offer."""

    offer_id = str(offer.get("offer_id") or "").strip()
    plan_id = str(offer.get("plan_id") or "").strip()

    if offer_id in ENTERPRISE_OFFER_IDS or plan_id in ENTERPRISE_PLAN_IDS:
        return deepcopy(ENTERPRISE_REVIEW_POLICY)

    return deepcopy(SELF_SERVICE_POLICY)


def apply_offer_fulfillment_policy(offer: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of offer with fulfillment metadata attached."""

    enriched = deepcopy(offer)
    policy = classify_offer_fulfillment(enriched)
    enriched.update(policy)
    return enriched
