import json

from fastapi.testclient import TestClient

from processual_api.main import app

SECRET_MARKERS = (
    "lemonsqueezy_api_key",
    "lemonsqueezy_webhook_secret",
    "provider_secret",
    "encrypted_key",
    "api_key",
)


def test_pricing_catalog_route_is_public_safe_without_lemon_config(monkeypatch) -> None:
    monkeypatch.delenv("LEMONSQUEEZY_API_KEY", raising=False)
    monkeypatch.delenv("LEMONSQUEEZY_STORE_ID", raising=False)
    monkeypatch.delenv("LEMONSQUEEZY_WEBHOOK_SECRET", raising=False)

    response = TestClient(app).get("/billing/pricing-catalog")

    assert response.status_code == 200

    payload = response.json()
    assert payload["pricing_status"] == "draft"
    assert payload["billing_policy"] == "byok"
    assert payload["provider_cost_included"] is False
    assert payload["checkout_enabled"] is False
    assert payload["plans"]


def test_pricing_catalog_route_does_not_expose_secret_markers() -> None:
    response = TestClient(app).get("/billing/pricing-catalog")

    assert response.status_code == 200

    serialized = json.dumps(response.json()).lower()
    for marker in SECRET_MARKERS:
        assert marker not in serialized


def test_pricing_catalog_route_keeps_checkout_disabled_for_all_plans() -> None:
    response = TestClient(app).get("/billing/pricing-catalog")

    assert response.status_code == 200

    payload = response.json()
    assert payload["checkout_enabled"] is False

    for plan in payload["plans"]:
        assert plan["checkout_enabled"] is False
        assert plan["monthly_price_usd"] is None
        assert plan["yearly_price_usd"] is None
