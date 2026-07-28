from __future__ import annotations

from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.main import app


def _client_for_user(user: dict[str, object]) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_checkout_options_show_tunisia_only_for_tunisian_address(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "true")
    client = _client_for_user(
        {
            "sub": "customer-tn",
            "billing_address": {"country_code": "TN"},
        }
    )

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "address_country_code": "TN",
        "eligible_channels": [
            "maestro_direct",
            "lemon_squeezy",
        ],
        "show_tunisia_payment_option": True,
        "customer_choice_allowed": True,
        "address_required": False,
    }


def test_checkout_options_hide_tunisia_for_non_tunisian_address(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "true")
    client = _client_for_user(
        {
            "sub": "customer-fr",
            "billing_address": {"country_code": "FR"},
        }
    )

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["eligible_channels"] == ["lemon_squeezy"]
    assert response.json()["show_tunisia_payment_option"] is False


def test_checkout_options_hide_tunisia_when_feature_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "false")
    client = _client_for_user(
        {
            "sub": "customer-tn",
            "billing_address": {"country_code": "TN"},
        }
    )

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["eligible_channels"] == ["lemon_squeezy"]
    assert response.json()["show_tunisia_payment_option"] is False
