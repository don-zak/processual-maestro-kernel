from processual_api.billing.offer_fulfillment_policy import (
    apply_offer_fulfillment_policy,
    classify_offer_fulfillment,
)


def test_starter_offer_is_self_service():
    offer = {"offer_id": "starter_monthly", "plan_id": "starter"}

    policy = classify_offer_fulfillment(offer)

    assert policy["fulfillment_mode"] == "self_service"
    assert policy["requires_supervisor_review"] is False
    assert policy["payment_required"] is True
    assert policy["activation_policy"] == "automatic_after_successful_payment"


def test_business_offer_is_self_service():
    offer = {"offer_id": "business_monthly", "plan_id": "business"}

    enriched = apply_offer_fulfillment_policy(offer)

    assert enriched["fulfillment_mode"] == "self_service"
    assert enriched["checkout_mode"] == "direct_checkout_when_approved"
    assert enriched["custom_quote_required"] is False


def test_enterprise_offer_requires_review():
    offer = {"offer_id": "enterprise_contact", "plan_id": "enterprise"}

    policy = classify_offer_fulfillment(offer)

    assert policy["fulfillment_mode"] == "enterprise_review"
    assert policy["requires_supervisor_review"] is True
    assert policy["payment_required"] is False
    assert policy["custom_quote_required"] is True
    assert policy["activation_policy"] == "manual_after_enterprise_review"


def test_policy_returns_copy_not_shared_state():
    offer = {"offer_id": "starter_monthly", "plan_id": "starter"}

    first = classify_offer_fulfillment(offer)
    first["requires_supervisor_review"] = True
    second = classify_offer_fulfillment(offer)

    assert second["requires_supervisor_review"] is False
