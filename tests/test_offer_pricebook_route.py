import json

from fastapi.testclient import TestClient

from processual_api.main import app

SECRET_MARKERS = (
    "lemonsqueezy_api_key",
    "lemonsqueezy_webhook_secret",
    "provider_secret",
    "encrypted_key",
    "api_key",
    "webhook_secret",
)

RETIRED_PUBLIC_ENTERPRISE = {
    "enterprise_pilot",
    "enterprise_core",
    "enterprise_scale",
    "enterprise_strategic",
}


def test_offer_pricebook_route_exposes_fixed_and_requirements_based_offers() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pricebook_status"] == "draft_review"
    assert payload["price_status"] == "selected_pricing_unpublished"
    assert payload["price_calculation_status"] == "derived_from_selected_pricing"
    assert payload["currency"] == "USD"
    assert payload["checkout_enabled"] is False

    offers = payload["offers"]
    by_id = {offer["offer_id"]: offer for offer in offers}
    assert set(by_id) == {
        "academic_monthly",
        "academic_annual",
        "starter_monthly",
        "starter_annual",
        "business_monthly",
        "business_annual",
        "enterprise_integration_trial_contact",
        "enterprise_deployment_contact",
    }

    for offer_id in {
        "academic_monthly",
        "academic_annual",
        "starter_monthly",
        "starter_annual",
        "business_monthly",
        "business_annual",
    }:
        offer = by_id[offer_id]
        assert offer["monthly_amount_cents"] > 0
        assert offer["annual_amount_cents"] > 0
        assert offer["usage_overage_unit_price_cents"] > 0
        assert offer["checkout_enabled"] is False

    for offer_id in {
        "enterprise_integration_trial_contact",
        "enterprise_deployment_contact",
    }:
        offer = by_id[offer_id]
        assert offer["billing_interval"] == "contact"
        assert offer["amount_cents"] is None
        assert offer["monthly_amount_cents"] is None
        assert offer["annual_amount_cents"] is None
        assert offer["usage_overage_unit_price_cents"] is None
        assert offer["monthly_unit_allowance"] is None
        assert offer["custom_quote_required"] is True
        assert offer["fulfillment_mode"] == "enterprise_review"
        assert offer["requires_supervisor_review"] is True
        assert offer["payment_required"] is False
        assert offer["checkout_mode"] == "contact_sales"
        assert offer["checkout_enabled"] is False


def test_offer_pricebook_route_quarantines_retired_enterprise_tiers() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")
    assert response.status_code == 200

    serialized = json.dumps(response.json()).lower()
    for retired in RETIRED_PUBLIC_ENTERPRISE:
        assert retired not in serialized

    assert "enterprise pilot" not in serialized
    assert "enterprise core" not in serialized
    assert "enterprise scale" not in serialized
    assert "enterprise strategic" not in serialized


def test_offer_pricebook_route_does_not_expose_secret_markers() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")

    assert response.status_code == 200
    serialized = json.dumps(response.json()).lower()
    for marker in SECRET_MARKERS:
        assert marker not in serialized
