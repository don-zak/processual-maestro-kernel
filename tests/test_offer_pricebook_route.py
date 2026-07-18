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


def test_offer_pricebook_route_is_public_safe_without_checkout_or_prices() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")

    assert response.status_code == 200

    payload = response.json()
    assert payload["pricebook_status"] == "draft_review"
    assert payload["price_status"] == "pending_review"
    assert payload["price_calculation_status"] == "not_defined"
    assert payload["currency"] is None
    assert payload["checkout_enabled"] is False
    assert payload["offers"]

    for offer in payload["offers"]:
        assert offer["currency"] is None
        assert offer["checkout_enabled"] is False
        assert offer["amount_cents"] is None
        assert offer["monthly_amount_cents"] is None
        assert offer["yearly_amount_cents"] is None
        assert offer["setup_fee_cents"] is None
        assert offer["minimum_commit_cents"] is None
        assert offer["usage_overage_unit_price_cents"] is None


def test_offer_pricebook_route_does_not_expose_secret_markers() -> None:
    response = TestClient(app).get("/billing/offer-pricebook")

    assert response.status_code == 200

    serialized = json.dumps(response.json()).lower()
    for marker in SECRET_MARKERS:
        assert marker not in serialized
