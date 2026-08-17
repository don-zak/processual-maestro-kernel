"""Versioned, non-activating commercial offer pricebook.

The offer pricebook derives plan identity, quota, entitlement metadata, and USD
pricing from the canonical commercial catalog. It does not approve publication,
enable checkout, bind provider variants, or create channel-specific settlement
records.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
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
from processual_api.billing.offer_fulfillment_policy import (
    apply_offer_fulfillment_policy,
)

OFFER_PRICEBOOK_VERSION = "2026-08-canonical-offers-v2"
OFFER_PRICEBOOK_STATUS = CATALOG_STATUS
OFFER_PRICE_STATUS = "selected_pricing_unpublished"

PRICE_REVIEW_LABEL = "Selected pricing — publication approval required"
PRICE_CALCULATION_STATUS = "derived_from_selected_pricing"
PRICE_REVIEW_NOTE = (
    "Prices are derived from the selected commercial pricing authority. "
    "Publication, checkout, settlement, and provider bindings remain disabled "
    "until their dedicated launch gates are approved."
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


def _money_cents(value: Decimal) -> int:
    return int((value * Decimal("100")).to_integral_exact())


def _offer_definitions() -> tuple[dict[str, Any], ...]:
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
                        "Canonical commercial plan prepared for assessment, scoping, "
                        "and explicit publication approval."
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
        "usage_overage_unit_price_cents": _money_cents(
            contract.overage_per_1000_usd
        ),
        "setup_fee_cents": None,
        "minimum_commit_cents": None,
    }
    if "amount_cents" in offer_definition:
        payload["amount_cents"] = offer_definition["amount_cents"]
    else:
        payload["amount_cents"] = None

    return apply_offer_fulfillment_policy(payload)


def list_offer_prices(*, include_unlisted: bool = True) -> list[dict[str, Any]]:
    """Return canonical offers while keeping publication and checkout disabled."""

    offers = [_offer_payload(definition) for definition in _offer_definitions()]
    if not include_unlisted:
        offers = [offer for offer in offers if offer["commercially_listed"]]
    return deepcopy(offers)


def get_offer_price(offer_id: str) -> dict[str, Any] | None:
    normalized_offer_id = str(offer_id or "").strip()
    for offer in list_offer_prices(include_unlisted=True):
        if offer["offer_id"] == normalized_offer_id:
            return deepcopy(offer)
    return None


def public_offer_pricebook() -> dict[str, Any]:
    """Return the public-safe canonical pricebook without launch activation."""

    offers = list_offer_prices(include_unlisted=False)
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
        "offers": offers,
    }
