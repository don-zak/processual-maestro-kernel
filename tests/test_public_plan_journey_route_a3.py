from decimal import Decimal

from fastapi.testclient import TestClient

from processual_api.billing.maestro_group1_selected_pricing import (
    DEFAULT_YEARLY_DISCOUNT_PERCENT,
)
from processual_api.main import app


def test_public_plan_journey_route_returns_catalog() -> None:
    response = TestClient(app).get("/billing/public-plan-journey")

    assert response.status_code == 200

    payload = response.json()

    assert payload["version"] == "2026-08-commercial-plan-pages-v1"
    assert payload["currency"] == "USD"
    assert payload["billing_periods"] == ["monthly", "annual"]
    assert payload["annual_discount_percent"] == int(DEFAULT_YEARLY_DISCOUNT_PERCENT)
    assert payload["annual_discount_scope"] == "base_plan_only"
    assert payload["public_price_ceiling_plan"] == "enterprise_pilot"
    assert payload["checkout_enabled"] is False
    assert payload["provider_cost_included"] is False
    assert len(payload["plans"]) == 9


def test_public_plan_journey_route_exposes_expected_prices() -> None:
    response = TestClient(app).get("/billing/public-plan-journey")
    payload = response.json()

    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
    multiplier = Decimal("1") - DEFAULT_YEARLY_DISCOUNT_PERCENT / Decimal("100")

    assert by_id["academic_individual"]["monthly_price_usd"] == "29.00"
    assert Decimal(by_id["academic_individual"]["annual_price_usd"]) == (
        Decimal("29") * Decimal("12") * multiplier
    ).quantize(Decimal("0.01"))
    assert by_id["starter"]["monthly_price_usd"] == "49.00"
    assert Decimal(by_id["starter"]["annual_price_usd"]) == (
        Decimal("49") * Decimal("12") * multiplier
    ).quantize(Decimal("0.01"))
    assert by_id["business"]["monthly_price_usd"] == "519.00"
    assert by_id["enterprise_pilot"]["monthly_price_usd"] == "2790.00"


def test_public_plan_journey_route_hides_assessment_prices() -> None:
    response = TestClient(app).get("/billing/public-plan-journey")
    payload = response.json()

    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}

    for plan_id in (
        "academic_institution",
        "enterprise_integration_starter",
        "enterprise_core",
        "enterprise_scale",
        "enterprise_strategic",
    ):
        assert by_id[plan_id]["monthly_price_usd"] is None
        assert by_id[plan_id]["annual_price_usd"] is None
        assert by_id[plan_id]["requires_assessment"] is True
        assert by_id[plan_id]["registration_available"] is False
        assert by_id[plan_id]["action"] == "request_assessment"
