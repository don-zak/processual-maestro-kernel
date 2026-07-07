"""Unit cost assumptions for Maestro pricing review.

This module intentionally contains no approved prices, no currency amount,
no checkout toggle, and no Lemon variant IDs.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

UNIT_COST_REVIEW: dict[str, Any] = {
    "unit_cost_review_version": "2026-07-08.08f",
    "review_status": "pending_review",
    "approved_for_pricing": False,
    "approved_for_checkout": False,
    "currency": None,
    "provider_cost_included": False,
    "billing_policy": "byok",
    "maestro_unit_definition": {
        "workflow_run_weight": None,
        "integration_action_weight": None,
        "document_processing_weight": None,
        "automation_run_weight": None,
        "supervisor_action_weight": None,
        "storage_retention_weight": None,
        "retry_error_overhead_weight": None,
    },
    "cost_components": {
        "infrastructure": {
            "server_or_cloud_run_cost_cents": None,
            "database_cost_cents": None,
            "cache_cost_cents": None,
            "storage_cost_cents": None,
            "logging_monitoring_cost_cents": None,
            "egress_cost_cents": None,
        },
        "payment_processing": {
            "processor": "lemon_squeezy",
            "merchant_of_record": True,
            "processor_percent": None,
            "processor_fixed_fee_cents": None,
            "subscription_extra_percent": None,
            "international_extra_percent": None,
            "paypal_extra_percent": None,
            "net_payout_formula_status": "pending_review",
        },
        "external_taxes": {
            "sales_tax_or_vat_handled_by_merchant_of_record": True,
            "tax_inclusive_pricing": None,
            "external_tax_impact_status": "pending_review",
        },
        "tunisia_local_taxes": {
            "vat_rate": None,
            "withholding_tax_rate": None,
            "corporate_tax_rate": None,
            "local_tax_reserve_cents": None,
            "accountant_review_required": True,
        },
        "operations": {
            "support_cost_cents": None,
            "supervision_cost_cents": None,
            "integration_cost_cents": None,
            "risk_buffer_cents": None,
        },
    },
    "pricing_formula_notes": [
        (
            "gross_customer_price must cover infrastructure, payment processing, "
            "external tax effects, local tax reserve, support, supervision, "
            "integration, and risk buffer."
        ),
        "AI provider costs are excluded under BYOK.",
        "Self-service offers can later use checkout only after approved price and Lemon variant mapping.",
        "Enterprise offers require review and custom quote before activation.",
    ],
}


def get_unit_cost_assumptions() -> dict[str, Any]:
    """Return a defensive copy of the unit cost review model."""

    return deepcopy(UNIT_COST_REVIEW)
