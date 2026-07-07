import json

from processual_api.billing.offer_pricebook import (
    OFFER_PRICE_STATUS,
    OFFER_PRICEBOOK_STATUS,
    OFFER_PRICEBOOK_VERSION,
    get_offer_price,
    list_offer_prices,
    public_offer_pricebook,
)
from processual_api.billing.subscription_catalog import get_subscription_plan
from processual_api.billing.usage_pricing import monthly_unit_allowance

SECRET_MARKERS = (
    "lemonsqueezy_api_key",
    "lemonsqueezy_webhook_secret",
    "provider_secret",
    "encrypted_key",
    "api_key",
    "webhook_secret",
)

PRICE_FIELDS = (
    "amount_cents",
    "monthly_amount_cents",
    "yearly_amount_cents",
    "setup_fee_cents",
    "minimum_commit_cents",
    "usage_overage_unit_price_cents",
)


def test_offer_pricebook_metadata_is_versioned_pending_review() -> None:
    payload = public_offer_pricebook()

    assert payload["pricebook_version"] == OFFER_PRICEBOOK_VERSION
    assert payload["pricebook_status"] == OFFER_PRICEBOOK_STATUS == "draft_review"
    assert payload["price_status"] == OFFER_PRICE_STATUS == "pending_review"
    assert payload["price_calculation_status"] == "not_defined"
    assert payload["currency"] is None
    assert payload["checkout_enabled"] is False
    assert payload["offers"]


def test_offer_pricebook_has_expected_offer_shapes_without_prices() -> None:
    offers = list_offer_prices(include_unlisted=False)
    offer_ids = {offer["offer_id"] for offer in offers}

    assert offer_ids == {
        "starter_trial",
        "starter_monthly",
        "starter_yearly",
        "business_monthly",
        "business_yearly",
        "enterprise_integration_starter_monthly",
        "enterprise_integration_starter_yearly",
        "enterprise_contact",
    }

    intervals = {offer["billing_interval"] for offer in offers}
    assert intervals == {"trial", "monthly", "yearly", "contact"}

    for offer in offers:
        assert offer["commercially_listed"] is True
        assert offer["price_status"] == "pending_review"
        assert offer["public_price_label"] == "Pricing pending review"
        assert offer["currency"] is None
        assert offer["checkout_enabled"] is False
        assert offer["approval_required_before_checkout"] is True
        assert offer["trial_duration_days"] is None

        for price_field in PRICE_FIELDS:
            assert offer[price_field] is None


def test_offer_pricebook_links_every_offer_to_subscription_catalog_and_allowance() -> None:
    for offer in list_offer_prices(include_unlisted=False):
        plan = get_subscription_plan(offer["plan_id"])

        assert plan is not None
        assert offer["plan_display_name"] == plan["display_name"]
        assert offer["monthly_unit_allowance"] == monthly_unit_allowance(offer["plan_id"])
        assert offer["allowance_source"] == "usage_pricing.monthly_unit_allowance"
        assert offer["billing_policy"] == "byok"
        assert offer["provider_cost_included"] is False


def test_get_offer_price_returns_copy_and_rejects_unknown() -> None:
    starter = get_offer_price("starter_monthly")

    assert starter is not None
    assert starter["offer_id"] == "starter_monthly"

    starter["display_name"] = "Mutated"

    fresh = get_offer_price("starter_monthly")
    assert fresh is not None
    assert fresh["display_name"] == "Starter Monthly"

    assert get_offer_price("professional_monthly") is None
    assert get_offer_price("unknown") is None
    assert get_offer_price("") is None


def test_public_offer_pricebook_is_secret_safe() -> None:
    serialized = json.dumps(public_offer_pricebook()).lower()

    for marker in SECRET_MARKERS:
        assert marker not in serialized


def test_paid_trial_and_enterprise_evaluation_have_distinct_public_policy() -> None:
    starter_trial = get_offer_price("starter_trial")
    enterprise_trial = get_offer_price("enterprise_integration_trial")

    assert starter_trial is not None
    assert starter_trial["offer_kind"] == "paid_trial"
    assert starter_trial["commercially_listed"] is True
    assert starter_trial["requires_supervisor_review"] is False
    assert starter_trial["refund_policy"]["refund_basis"] == "operational_outcome_not_achieved"
    assert "program_runs" in starter_trial["refund_policy"]["success_criteria"]
    assert "tasks_execute" in starter_trial["refund_policy"]["success_criteria"]
    assert "results_are_obtained" in starter_trial["refund_policy"]["success_criteria"]
    assert (
        "customer_failed_to_connect_external_agents"
        in starter_trial["refund_policy"]["excluded_refund_reasons"]
    )
    assert (
        "trial_period_expired_before_usage_quantity_completed"
        in starter_trial["refund_policy"]["excluded_refund_reasons"]
    )

    assert enterprise_trial is not None
    assert enterprise_trial["offer_kind"] == "enterprise_evaluation"
    assert enterprise_trial["commercially_listed"] is False
    assert enterprise_trial["excluded_from_general_paid_trial"] is True
    assert enterprise_trial["requires_supervisor_review"] is True
    assert enterprise_trial["requires_preparation"] is True
