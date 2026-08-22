from pathlib import Path

from processual_api.billing.commercial_catalog_contracts import (
    OfferVisibility,
    build_catalog_plan_contracts,
)
from processual_api.billing.offer_pricebook import (
    OFFER_PRICEBOOK_STATUS,
    list_offer_prices,
    public_offer_pricebook,
)


def test_offer_pricebook_uses_only_canonical_plan_codes() -> None:
    contracts = {contract.plan_code: contract for contract in build_catalog_plan_contracts()}
    offers = list_offer_prices(include_unlisted=True)

    assert offers
    assert {offer["plan_id"] for offer in offers} == set(contracts)
    assert "enterprise" not in {offer["plan_id"] for offer in offers}
    assert "enterprise_integration" not in {offer["plan_id"] for offer in offers}
    assert "pilot_starter" not in {offer["plan_id"] for offer in offers}


def test_offer_numeric_values_derive_from_canonical_commercial_contracts() -> None:
    contracts = {contract.plan_code: contract for contract in build_catalog_plan_contracts()}

    for offer in list_offer_prices(include_unlisted=True):
        contract = contracts[offer["plan_id"]]
        assert offer["monthly_unit_allowance"] == contract.included_maestro_units
        assert offer["monthly_amount_cents"] == int(contract.monthly_price_usd * 100)
        assert offer["annual_amount_cents"] == int(contract.annual_price_usd * 100)
        assert offer["usage_overage_unit_price_cents"] == int(
            contract.overage_per_1000_usd * 100
        )
        assert offer["allowance_source"] == "commercial_catalog_contracts"
        assert offer["pricing_source"] == "maestro_group1_selected_pricing"


def test_offer_pricebook_remains_non_activating_until_publication_gate() -> None:
    pricebook = public_offer_pricebook()

    assert OFFER_PRICEBOOK_STATUS == "draft_review"
    assert pricebook["checkout_enabled"] is False
    assert pricebook["currency"] == "USD"
    for offer in pricebook["offers"]:
        assert offer["checkout_enabled"] is False
        assert offer["approval_required_before_checkout"] is True


def test_enterprise_catalog_plans_remain_review_fulfillment() -> None:
    contracts = {contract.plan_code: contract for contract in build_catalog_plan_contracts()}
    offers = list_offer_prices(include_unlisted=True)

    for offer in offers:
        contract = contracts[offer["plan_id"]]
        if contract.visibility is OfferVisibility.PUBLIC_CANDIDATE:
            assert offer["fulfillment_mode"] == "self_service"
            continue
        assert offer["fulfillment_mode"] == "enterprise_review"
        assert offer["checkout_mode"] == "contact_sales"
        assert offer["custom_quote_required"] is True


def test_legacy_catalog_modules_cannot_reenter_offer_pricebook_authority() -> None:
    source = Path("processual_api/billing/offer_pricebook.py").read_text(encoding="utf-8")

    assert "subscription_catalog" not in source
    assert "usage_pricing" not in source
    assert "get_subscription_plan" not in source
    assert "monthly_unit_allowance(" not in source
