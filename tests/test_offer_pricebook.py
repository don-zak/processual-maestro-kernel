import json
from decimal import Decimal

from processual_api.billing.commercial_catalog_contracts import (
    CATALOG_CONTRACT_VERSION,
    OfferVisibility,
    build_catalog_plan_contracts,
)
from processual_api.billing.maestro_group1_selected_pricing import (
    SELECTED_PROPOSAL_VERSION,
)
from processual_api.billing.offer_pricebook import (
    OFFER_PRICE_STATUS,
    OFFER_PRICEBOOK_STATUS,
    OFFER_PRICEBOOK_VERSION,
    get_offer_price,
    list_offer_prices,
    public_offer_pricebook,
)

SECRET_MARKERS = (
    "lemonsqueezy_api_key",
    "lemonsqueezy_webhook_secret",
    "provider_secret",
    "encrypted_key",
    "api_key",
    "webhook_secret",
)


def _cents(value: Decimal) -> int:
    return int((value * Decimal("100")).to_integral_exact())


def test_offer_pricebook_metadata_is_versioned_and_fail_closed() -> None:
    payload = public_offer_pricebook()

    assert payload["pricebook_version"] == OFFER_PRICEBOOK_VERSION
    assert payload["pricebook_status"] == OFFER_PRICEBOOK_STATUS == "draft_review"
    assert payload["price_status"] == OFFER_PRICE_STATUS == "selected_pricing_unpublished"
    assert payload["price_calculation_status"] == "derived_from_selected_pricing"
    assert payload["pricing_version"] == SELECTED_PROPOSAL_VERSION
    assert payload["catalog_contract_version"] == CATALOG_CONTRACT_VERSION
    assert payload["currency"] == "USD"
    assert payload["checkout_enabled"] is False
    assert payload["offers"]


def test_offer_pricebook_shapes_follow_canonical_catalog_visibility() -> None:
    contracts = build_catalog_plan_contracts()
    offers = list_offer_prices(include_unlisted=False)
    by_id = {offer["offer_id"]: offer for offer in offers}

    expected_ids: set[str] = set()
    for contract in contracts:
        if contract.visibility is OfferVisibility.PUBLIC_CANDIDATE:
            expected_ids.update(
                {
                    f"{contract.plan_code}_monthly",
                    f"{contract.plan_code}_annual",
                }
            )
        else:
            expected_ids.add(f"{contract.plan_code}_contact")

    assert set(by_id) == expected_ids
    assert {offer["billing_interval"] for offer in offers} == {
        "monthly",
        "annual",
        "contact",
    }


def test_offer_pricebook_derives_prices_quotas_and_entitlements_from_canonical_contracts() -> None:
    contracts = {item.plan_code: item for item in build_catalog_plan_contracts()}

    for offer in list_offer_prices(include_unlisted=False):
        contract = contracts[offer["plan_id"]]

        assert offer["commercially_listed"] is True
        assert offer["price_status"] == "selected_pricing_unpublished"
        assert offer["currency"] == "USD"
        assert offer["checkout_enabled"] is False
        assert offer["approval_required_before_checkout"] is True
        assert offer["trial_duration_days"] is None
        assert offer["monthly_unit_allowance"] == contract.included_maestro_units
        assert offer["allowance_source"] == "commercial_catalog_contracts"
        assert offer["pricing_source"] == "maestro_group1_selected_pricing"
        assert offer["pricing_source_version"] == SELECTED_PROPOSAL_VERSION
        assert offer["catalog_contract_version"] == CATALOG_CONTRACT_VERSION
        assert offer["monthly_amount_cents"] == _cents(contract.monthly_price_usd)
        assert offer["annual_amount_cents"] == _cents(contract.annual_price_usd)
        assert offer["usage_overage_unit_price_cents"] == _cents(
            contract.overage_per_1000_usd
        )
        assert offer["entitlement_codes"] == [item.value for item in contract.entitlements]
        assert offer["setup_fee_cents"] is None
        assert offer["minimum_commit_cents"] is None
        assert offer["provider_cost_included"] is False

        if offer["billing_interval"] == "monthly":
            assert offer["amount_cents"] == _cents(contract.monthly_price_usd)
        elif offer["billing_interval"] == "annual":
            assert offer["amount_cents"] == _cents(contract.annual_price_usd)
        else:
            assert offer["amount_cents"] is None


def test_get_offer_price_returns_copy_and_rejects_legacy_or_unknown_ids() -> None:
    starter = get_offer_price("starter_monthly")

    assert starter is not None
    assert starter["offer_id"] == "starter_monthly"

    starter["display_name"] = "Mutated"

    fresh = get_offer_price("starter_monthly")
    assert fresh is not None
    assert fresh["display_name"] == "Starter Monthly"

    assert get_offer_price("starter_trial") is None
    assert get_offer_price("professional_monthly") is None
    assert get_offer_price("enterprise_contact") is None
    assert get_offer_price("unknown") is None
    assert get_offer_price("") is None


def test_public_offer_pricebook_is_secret_safe() -> None:
    serialized = json.dumps(public_offer_pricebook()).lower()

    for marker in SECRET_MARKERS:
        assert marker not in serialized


def test_enterprise_offers_remain_review_only_and_not_direct_checkout() -> None:
    for contract in build_catalog_plan_contracts():
        if contract.visibility is OfferVisibility.PUBLIC_CANDIDATE:
            continue

        offer = get_offer_price(f"{contract.plan_code}_contact")
        assert offer is not None
        assert offer["offer_kind"] == "enterprise_evaluation"
        assert offer["public_offer"] is False
        assert offer["excluded_from_general_paid_trial"] is True
        assert offer["requires_supervisor_review"] is True
        assert offer["requires_preparation"] is True
        assert offer["requires_scoping"] is True
        assert offer["payment_required"] is False
        assert offer["activation_policy"] == "manual_after_enterprise_review"
        assert offer["checkout_mode"] == "contact_sales"
        assert offer["custom_quote_required"] is True
        assert offer["checkout_enabled"] is False
