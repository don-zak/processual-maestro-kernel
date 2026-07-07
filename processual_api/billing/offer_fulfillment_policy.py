"""Offer fulfillment policy for pricing and checkout readiness.

This module does not approve prices and does not enable checkout.
It classifies offers as paid-trial, self-service, or enterprise-review.
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


PAID_TRIAL_REFUND_POLICY: dict[str, Any] = {
    "refund_review_available": True,
    "refund_basis": "operational_outcome_not_achieved",
    "success_criteria": [
        "program_runs",
        "tasks_execute",
        "results_are_obtained",
    ],
    "excluded_refund_reasons": [
        "customer_failed_to_connect_external_agents",
        "customer_provider_or_credential_issue",
        "customer_delay_or_missing_requirements",
        "trial_period_expired_before_usage_quantity_completed",
        "unused_units_after_period_expiry",
    ],
    "refund_type": "full_or_partial_after_review",
    "legal_review_required": True,
}

PAID_TRIAL_POLICY: dict[str, Any] = {
    "offer_kind": "paid_trial",
    "public_offer": True,
    "excluded_from_general_paid_trial": False,
    "requires_preparation": False,
    "requires_scoping": False,
    "fulfillment_mode": "paid_trial",
    "requires_supervisor_review": False,
    "registration_required": True,
    "payment_required": True,
    "activation_policy": "automatic_after_successful_payment",
    "checkout_mode": "direct_checkout_when_approved",
    "custom_quote_required": False,
    "trial_contents_status": "pending_review",
    "refund_policy": PAID_TRIAL_REFUND_POLICY,
}

ENTERPRISE_REVIEW_POLICY: dict[str, Any] = {
    "offer_kind": "enterprise_evaluation",
    "public_offer": False,
    "excluded_from_general_paid_trial": True,
    "requires_preparation": True,
    "requires_scoping": True,
    "fulfillment_mode": "enterprise_review",
    "requires_supervisor_review": True,
    "registration_required": True,
    "payment_required": False,
    "activation_policy": "manual_after_enterprise_review",
    "checkout_mode": "contact_sales",
    "custom_quote_required": True,
}


PAID_TRIAL_OFFER_IDS = {
    "starter_trial",
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

    if offer_id in PAID_TRIAL_OFFER_IDS:
        return deepcopy(PAID_TRIAL_POLICY)

    if offer_id in ENTERPRISE_OFFER_IDS or plan_id in ENTERPRISE_PLAN_IDS:
        return deepcopy(ENTERPRISE_REVIEW_POLICY)

    return deepcopy(SELF_SERVICE_POLICY)


def apply_offer_fulfillment_policy(offer: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of offer with fulfillment metadata attached."""

    enriched = deepcopy(offer)
    policy = classify_offer_fulfillment(enriched)
    enriched.update(policy)
    return enriched
