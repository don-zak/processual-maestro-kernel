import json

from fastapi.testclient import TestClient

from processual_api.main import app

SECRET_MARKERS = (
    "api_key",
    "secret",
    "password",
    "bearer ",
    "private_key",
    "lemon_variant",
    "variant_id",
)


def test_unit_cost_assumptions_route_returns_public_safe_review_model() -> None:
    response = TestClient(app).get("/billing/unit-cost-assumptions")

    assert response.status_code == 200

    payload = response.json()
    assert payload["review_status"] == "pending_review"
    assert payload["approved_for_pricing"] is False
    assert payload["approved_for_checkout"] is False
    assert payload["currency"] is None
    assert payload["provider_cost_included"] is False
    assert payload["billing_policy"] == "byok"


def test_unit_cost_assumptions_route_includes_required_cost_components() -> None:
    response = TestClient(app).get("/billing/unit-cost-assumptions")

    assert response.status_code == 200

    components = response.json()["cost_components"]
    assert "infrastructure" in components
    assert "payment_processing" in components
    assert "external_taxes" in components
    assert "tunisia_local_taxes" in components
    assert "operations" in components

    assert components["payment_processing"]["processor"] == "lemon_squeezy"
    assert components["payment_processing"]["merchant_of_record"] is True
    assert components["external_taxes"]["sales_tax_or_vat_handled_by_merchant_of_record"] is True
    assert components["tunisia_local_taxes"]["accountant_review_required"] is True


def test_unit_cost_assumptions_route_does_not_expose_secret_markers() -> None:
    response = TestClient(app).get("/billing/unit-cost-assumptions")

    assert response.status_code == 200

    serialized = json.dumps(response.json()).lower()
    for marker in SECRET_MARKERS:
        assert marker not in serialized


def test_unit_cost_assumptions_route_is_registered_static() -> None:
    source = open("processual_api/billing/router.py", encoding="utf-8").read()

    assert '@router.get("/unit-cost-assumptions")' in source
    assert "build_unit_cost_assumptions()" in source
    assert "public-safe draft unit cost assumptions model" in source
