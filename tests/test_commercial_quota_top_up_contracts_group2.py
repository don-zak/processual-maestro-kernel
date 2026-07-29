from decimal import Decimal

import pytest

from processual_api.billing.commercial_quota_top_up_contracts import (
    TOP_UP_CHECKOUT_ENABLED,
    TOP_UP_GRANT_ENABLED,
    TOP_UP_MULTIPLES_ONLY,
    TOP_UP_PERSISTENCE_ENABLED,
    TOP_UP_PURCHASE_ENABLED,
    TOP_UP_SEAT_BASED,
    TopUpPurchaseState,
    build_top_up_contract_bundle,
    build_top_up_policies,
    quote_top_up,
)


def test_top_up_policies_cover_all_catalog_plans() -> None:
    policies = build_top_up_policies()
    assert [policy.plan_code for policy in policies] == [
        "academic",
        "starter",
        "enterprise_integration_starter",
        "business",
        "enterprise_pilot",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ]


def test_minimum_bundle_sizes_are_explicit() -> None:
    policies = {policy.plan_code: policy for policy in build_top_up_policies()}
    assert policies["academic"].bundle_units == 5_000
    assert policies["starter"].bundle_units == 10_000
    assert policies["business"].bundle_units == 25_000
    assert policies["enterprise_pilot"].bundle_units == 100_000
    assert policies["enterprise_core"].bundle_units == 250_000
    assert policies["enterprise_scale"].bundle_units == 500_000


def test_bundle_prices_derive_from_plan_overage_rate() -> None:
    policies = {policy.plan_code: policy for policy in build_top_up_policies()}
    assert policies["academic"].price_per_bundle_usd == Decimal("32.50")
    assert policies["starter"].price_per_bundle_usd == Decimal("59.00")
    assert policies["business"].price_per_bundle_usd == Decimal("150.00")
    assert policies["enterprise_pilot"].price_per_bundle_usd == Decimal("650.00")


def test_valid_multiple_builds_price_preview() -> None:
    quote = quote_top_up("starter", 20_000)
    assert quote.bundle_count == 2
    assert quote.total_units == 20_000
    assert quote.total_price_usd == Decimal("118.00")
    assert quote.purchase_enabled is False
    assert quote.state in {
        TopUpPurchaseState.DISABLED,
        TopUpPurchaseState.UPGRADE_RECOMMENDED,
    }


def test_below_minimum_and_invalid_multiple_fail_closed() -> None:
    below = quote_top_up("starter", 5_000)
    invalid = quote_top_up("starter", 15_000)
    assert below.state is TopUpPurchaseState.BELOW_MINIMUM
    assert invalid.state is TopUpPurchaseState.INVALID_MULTIPLE
    assert below.total_price_usd == Decimal("0.00")
    assert invalid.total_price_usd == Decimal("0.00")


def test_above_maximum_fails_closed() -> None:
    quote = quote_top_up("academic", 25_000)
    assert quote.state is TopUpPurchaseState.ABOVE_MAXIMUM
    assert quote.bundle_count == 0


def test_upgrade_is_recommended_when_cheaper_or_equal() -> None:
    quote = quote_top_up("starter", 10_000)
    assert quote.upgrade_plan_code == "business"
    assert quote.upgrade_monthly_difference_usd == Decimal("470.00")

    quote = quote_top_up("starter", 80_000)
    assert quote.total_price_usd == Decimal("472.00")
    assert quote.state is TopUpPurchaseState.UPGRADE_RECOMMENDED


def test_unknown_plan_and_non_positive_request_are_rejected() -> None:
    with pytest.raises(ValueError):
        quote_top_up("unknown", 10_000)
    with pytest.raises(ValueError):
        quote_top_up("starter", 0)


def test_top_up_foundation_remains_non_activating() -> None:
    assert TOP_UP_PURCHASE_ENABLED is False
    assert TOP_UP_CHECKOUT_ENABLED is False
    assert TOP_UP_GRANT_ENABLED is False
    assert TOP_UP_PERSISTENCE_ENABLED is False
    assert TOP_UP_MULTIPLES_ONLY is True
    assert TOP_UP_SEAT_BASED is False

    bundle = build_top_up_contract_bundle()
    assert bundle["status"] == "draft_review"
    assert bundle["purchase_enabled"] is False
    assert bundle["checkout_enabled"] is False
    assert bundle["grant_enabled"] is False
    assert bundle["persistence_enabled"] is False
