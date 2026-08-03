from fastapi.testclient import TestClient

from processual_api.main import app


def test_public_plan_journey_route_returns_catalog() -> None:
    response = TestClient(app).get("/billing/public-plan-journey")

    assert response.status_code == 200

    payload = response.json()

    assert payload["version"] == "2026-08-plan-led-registration-v1"
    assert payload["currency"] == "USD"
    assert payload["billing_period"] == "monthly"
    assert payload["public_price_ceiling_plan"] == "enterprise_pilot"
    assert payload["checkout_enabled"] is False
    assert payload["provider_cost_included"] is False
    assert len(payload["plans"]) == 8


def test_public_plan_journey_route_exposes_expected_prices() -> None:
    response = TestClient(app).get("/billing/public-plan-journey")
    payload = response.json()

    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    assert by_id["academic"]["monthly_price_usd"] == "29"
    assert by_id["starter"]["monthly_price_usd"] == "49"
    assert by_id["business"]["monthly_price_usd"] == "519"
    assert by_id["enterprise_integration_starter"]["monthly_price_usd"] == "259"
    assert by_id["enterprise_pilot"]["monthly_price_usd"] == "2790"


def test_public_plan_journey_route_hides_post_pilot_prices() -> None:
    response = TestClient(app).get("/billing/public-plan-journey")
    payload = response.json()

    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    for plan_id in (
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ):
        assert by_id[plan_id]["monthly_price_usd"] is None
        assert by_id[plan_id]["requires_assessment"] is True
        assert by_id[plan_id]["registration_available"] is False
        assert by_id[plan_id]["action"] == "request_assessment"
