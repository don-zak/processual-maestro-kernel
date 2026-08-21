"""Versioned, non-activating commercial offer pricebook.

Internal historical offer identities remain readable for compatibility and audit,
but the public-safe pricebook exposes only current catalog subscriptions plus the
requirements-based Enterprise Integration Trial and Enterprise Deployment stages.
No public enterprise evaluation/deployment price or quota is derived from retired
internal tier pricing.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any, Final

from processual_api.billing.commercial_catalog_contracts import (
    CATALOG_CONTRACT_VERSION,
    CATALOG_STATUS,
    OfferVisibility,
    build_catalog_plan_contracts,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    SELECTED_PROPOSAL_VERSION,
)
from processual_api.billing.offer_fulfillment_policy import (
    apply_offer_fulfillment_policy,
)

OFFER_PRICEBOOK_VERSION = "2026-08-canonical-offers-v3"
OFFER_PRICEBOOK_STATUS = CATALOG_STATUS
OFFER_PRICE_STATUS = "selected_pricing_unpublished"

PRICE_REVIEW_LABEL = "Selected pricing — publication approval required"
PRICE_CALCULATION_STATUS = "derived_from_selected_pricing"
PRICE_REVIEW_NOTE = (
    "Eligible fixed-price offers derive from the selected commercial pricing authority. "
    "Enterprise evaluation and deployment terms are requirements-based and intentionally "
    "publish no fixed price or quota. Checkout, settlement, and provider bindings remain "
    "disabled until their dedicated launch gates are approved."
)

_PROVIDER_COST_NOTE = (
    "Provider/API usage is BYOK and is not included in the Maestro commercial price."
)

_DISPLAY_NAMES: dict[str, str] = {
    "academic": "Academic Individual",
    "starter": "Starter",
    "enterprise_integration_starter": "Enterprise Integration Trial",
    "business": "Business",
    "enterprise_pilot": "Enterprise Pilot",
    "enterprise_core": "Enterprise Core",
    "enterprise_scale": "Enterprise Scale",
    "enterprise_strategic": "Enterprise Strategic",
}

PUBLIC_FIXED_PRICE_PLAN_CODES: Final[frozenset[str]] = frozenset(
    {"academic", "starter", "business"}
)
PUBLIC_ENTERPRISE_TRIAL_SOURCE: Final[str] = "enterprise_integration_starter"
RETIRED_PUBLIC_ENTERPRISE_PLAN_CODES: Final[frozenset[str]] = frozenset(
    {"enterprise_pilot", "enterprise_core", "enterprise_scale", "enterprise_strategic"}
)


def _money_cents(value: Decimal) -> int:
    return int((value * Decimal("100")).to_integral_exact())


def _offer_definitions() -> tuple[dict[str, Any], ...]:
    """Build the internal compatibility pricebook.

    Historical enterprise identities remain here until a separately proven data
    migration can remove them without breaking persisted references. This function
    is not the public exposure boundary.
    """

    definitions: list[dict[str, Any]] = []
    for contract in build_catalog_plan_contracts():
        plan_code = contract.plan_code
        display_name = _DISPLAY_NAMES[plan_code]
        requires_sales_contact = contract.visibility is not OfferVisibility.PUBLIC_CANDIDATE

        if requires_sales_contact:
            definitions.append(
                {
                    "offer_id": f"{plan_code}_contact",
                    "plan_id": plan_code,
                    "plan_display_name": display_name,
                    "display_name": f"{display_name} — Commercial Review",
                    "description": (
                        "Internal compatibility offer retained for assessment, scoping, "
                        "and historical reference."
                    ),
                    "billing_interval": "contact",
                    "commercially_listed": True,
                    "requires_sales_contact": True,
                    "monthly_amount_cents": _money_cents(contract.monthly_price_usd),
                    "annual_amount_cents": _money_cents(contract.annual_price_usd),
                }
            )
            continue

        for interval, amount in (
            ("monthly", contract.monthly_price_usd),
            ("annual", contract.annual_price_usd),
        ):
            definitions.append(
                {
                    "offer_id": f"{plan_code}_{interval}",
                    "plan_id": plan_code,
                    "plan_display_name": display_name,
                    "display_name": f"{display_name} {interval.title()}",
                    "description": (
                        f"Canonical {interval} offer for {display_name}; "
                        "publication approval is still required."
                    ),
                    "billing_interval": interval,
                    "commercially_listed": True,
                    "requires_sales_contact": False,
                    "amount_cents": _money_cents(amount),
                }
            )

    return tuple(definitions)


def _contract_by_plan() -> dict[str, Any]:
    return {contract.plan_code: contract for contract in build_catalog_plan_contracts()}


def _offer_payload(offer_definition: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(offer_definition["plan_id"])
    contract = _contract_by_plan().get(plan_id)
    if contract is None:
        raise ValueError(f"Unknown canonical commercial plan for offer: {plan_id}")

    payload = {
        "offer_id": offer_definition["offer_id"],
        "plan_id": plan_id,
        "plan_display_name": offer_definition["plan_display_name"],
        "display_name": offer_definition["display_name"],
        "description": offer_definition["description"],
        "billing_interval": offer_definition["billing_interval"],
        "trial_duration_days": None,
        "commercially_listed": bool(offer_definition["commercially_listed"]),
        "requires_sales_contact": bool(offer_definition["requires_sales_contact"]),
        "pricebook_version": OFFER_PRICEBOOK_VERSION,
        "pricebook_status": OFFER_PRICEBOOK_STATUS,
        "price_status": OFFER_PRICE_STATUS,
        "public_price_label": PRICE_REVIEW_LABEL,
        "price_calculation_status": PRICE_CALCULATION_STATUS,
        "price_review_note": PRICE_REVIEW_NOTE,
        "price_inputs_pending_review": [
            "publication_approval",
            "channel_binding",
            "settlement_readiness",
        ],
        "currency": "USD",
        "checkout_enabled": False,
        "approval_required_before_checkout": True,
        "monthly_unit_allowance": contract.included_maestro_units,
        "allowance_source": "commercial_catalog_contracts",
        "pricing_source": "maestro_group1_selected_pricing",
        "pricing_source_version": SELECTED_PROPOSAL_VERSION,
        "catalog_contract_version": CATALOG_CONTRACT_VERSION,
        "provider_cost_included": False,
        "provider_cost_note": _PROVIDER_COST_NOTE,
        "entitlement_codes": [item.value for item in contract.entitlements],
        "monthly_amount_cents": _money_cents(contract.monthly_price_usd),
        "annual_amount_cents": _money_cents(contract.annual_price_usd),
        "usage_overage_unit_price_cents": _money_cents(contract.overage_per_1000_usd),
        "setup_fee_cents": None,
        "minimum_commit_cents": None,
    }
    payload["amount_cents"] = offer_definition.get("amount_cents")
    return apply_offer_fulfillment_policy(payload)


def list_offer_prices(*, include_unlisted: bool = True) -> list[dict[str, Any]]:
    """Return the internal compatibility offers without granting publication authority."""

    offers = [_offer_payload(definition) for definition in _offer_definitions()]
    if not include_unlisted:
        offers = [offer for offer in offers if offer["commercially_listed"]]
    return deepcopy(offers)


def get_offer_price(offer_id: str) -> dict[str, Any] | None:
    """Internal compatibility lookup; not a public exposure boundary."""

    normalized_offer_id = str(offer_id or "").strip()
    for offer in list_offer_prices(include_unlisted=True):
        if offer["offer_id"] == normalized_offer_id:
            return deepcopy(offer)
    return None


def _public_fixed_price_offers() -> list[dict[str, Any]]:
    offers = list_offer_prices(include_unlisted=False)
    return [
        offer
        for offer in offers
        if offer["plan_id"] in PUBLIC_FIXED_PRICE_PLAN_CODES
        and offer["billing_interval"] in {"monthly", "annual"}
    ]


def _public_enterprise_trial_offer() -> dict[str, Any]:
    internal = get_offer_price(f"{PUBLIC_ENTERPRISE_TRIAL_SOURCE}_contact")
    if internal is None:
        raise ValueError("Enterprise Integration Trial compatibility source is unavailable")

    public = deepcopy(internal)
    public.update(
        {
            "offer_id": "enterprise_integration_trial_contact",
            "plan_id": "enterprise_integration_starter",
            "plan_display_name": "Enterprise Integration Trial",
            "display_name": "Enterprise Integration Trial — Scope Assessment",
            "description": (
                "One-month governed enterprise integration evaluation with quota, integration "
                "scope, security review, and acceptance criteria defined from customer requirements."
            ),
            "billing_interval": "contact",
            "trial_duration_days": 30,
            "commercially_listed": True,
            "requires_sales_contact": True,
            "price_status": "requirements_based_quote",
            "public_price_label": "Pricing defined after assessment",
            "price_calculation_status": "not_publicly_fixed",
            "monthly_unit_allowance": None,
            "allowance_source": "approved_customer_scope",
            "pricing_source": "customer_requirements_and_contract",
            "monthly_amount_cents": None,
            "annual_amount_cents": None,
            "usage_overage_unit_price_cents": None,
            "amount_cents": None,
            "custom_quote_required": True,
            "checkout_enabled": False,
        }
    )
    return public


def _public_enterprise_deployment_offer() -> dict[str, Any]:
    return {
        "offer_id": "enterprise_deployment_contact",
        "plan_id": "enterprise_deployment",
        "plan_display_name": "Enterprise Deployment",
        "display_name": "Enterprise Deployment — Requirements Proposal",
        "description": (
            "Production-oriented enterprise deployment whose capacity, integration, support, SLA, "
            "security, rollout, and commercial terms are defined from an approved customer specification."
        ),
        "billing_interval": "contact",
        "trial_duration_days": None,
        "commercially_listed": True,
        "requires_sales_contact": True,
        "pricebook_version": OFFER_PRICEBOOK_VERSION,
        "pricebook_status": OFFER_PRICEBOOK_STATUS,
        "price_status": "requirements_based_quote",
        "public_price_label": "Commercial proposal after requirements review",
        "price_calculation_status": "not_publicly_fixed",
        "price_review_note": PRICE_REVIEW_NOTE,
        "price_inputs_pending_review": [
            "customer_specification",
            "capacity_and_integration_scope",
            "support_and_sla_terms",
            "commercial_approval",
        ],
        "currency": "USD",
        "checkout_enabled": False,
        "approval_required_before_checkout": True,
        "monthly_unit_allowance": None,
        "allowance_source": "approved_customer_specification",
        "pricing_source": "customer_requirements_and_contract",
        "pricing_source_version": None,
        "catalog_contract_version": CATALOG_CONTRACT_VERSION,
        "provider_cost_included": False,
        "provider_cost_note": _PROVIDER_COST_NOTE,
        "entitlement_codes": [],
        "monthly_amount_cents": None,
        "annual_amount_cents": None,
        "usage_overage_unit_price_cents": None,
        "setup_fee_cents": None,
        "minimum_commit_cents": None,
        "amount_cents": None,
        "custom_quote_required": True,
        "offer_kind": "enterprise_deployment",
        "public_offer": True,
        "excluded_from_general_paid_trial": True,
        "requires_supervisor_review": True,
        "requires_preparation": True,
        "requires_scoping": True,
        "payment_required": False,
        "activation_policy": "manual_after_enterprise_review",
        "checkout_mode": "contact_sales",
    }


def public_offer_pricebook() -> dict[str, Any]:
    """Return the public-safe pricebook with retired enterprise tiers quarantined."""

    offers = [
        *_public_fixed_price_offers(),
        _public_enterprise_trial_offer(),
        _public_enterprise_deployment_offer(),
    ]
    exposed_plan_ids = {str(offer["plan_id"]) for offer in offers}
    if exposed_plan_ids.intersection(RETIRED_PUBLIC_ENTERPRISE_PLAN_CODES):
        raise RuntimeError("Retired enterprise tiers leaked into the public offer pricebook")

    return {
        "pricebook_version": OFFER_PRICEBOOK_VERSION,
        "pricing_version": SELECTED_PROPOSAL_VERSION,
        "catalog_contract_version": CATALOG_CONTRACT_VERSION,
        "pricebook_status": OFFER_PRICEBOOK_STATUS,
        "price_status": OFFER_PRICE_STATUS,
        "public_price_label": PRICE_REVIEW_LABEL,
        "price_calculation_status": PRICE_CALCULATION_STATUS,
        "price_review_note": PRICE_REVIEW_NOTE,
        "currency": "USD",
        "provider_cost_included": False,
        "checkout_enabled": False,
        "offers": deepcopy(offers),
    }
