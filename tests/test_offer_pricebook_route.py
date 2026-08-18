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


def test_offer_pricebook_route_exposes_selected_prices_but_keeps_checkout_closed() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")

    assert response.status_code == 200

    payload = response.json()
    assert payload["pricebook_status"] == "draft_review"
    assert payload["price_status"] == "selected_pricing_unpublished"
    assert payload["price_calculation_status"] == "derived_from_selected_pricing"
    assert payload["currency"] == "USD"
    assert payload["checkout_enabled"] is False
    assert payload["offers"]

    for offer in payload["offers"]:
        assert offer["currency"] == "USD"
        assert offer["checkout_enabled"] is False
        assert offer["approval_required_before_checkout"] is True
        assert offer["monthly_amount_cents"] > 0
        assert offer["annual_amount_cents"] > 0
        assert offer["usage_overage_unit_price_cents"] > 0
        assert offer["setup_fee_cents"] is None
        assert offer["minimum_commit_cents"] is None

        if offer["billing_interval"] in {"monthly", "annual"}:
            assert offer["amount_cents"] > 0
        else:
            assert offer["billing_interval"] == "contact"
            assert offer["amount_cents"] is None


def test_offer_pricebook_route_does_not_expose_secret_markers() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")

    assert response.status_code == 200

    serialized = json.dumps(response.json()).lower()
    for marker in SECRET_MARKERS:
        assert marker not in serialized
