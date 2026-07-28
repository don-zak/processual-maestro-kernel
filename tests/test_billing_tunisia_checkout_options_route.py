from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import processual_api.billing.router as billing_router
from processual_api.auth.security import get_current_user
from processual_api.db import get_session
from processual_api.main import app

USER_ID = uuid.uuid4()


class FakeSession:
    pass


def _current_user() -> dict[str, object]:
    return {
        "sub": str(USER_ID),
        "user_id": str(USER_ID),
        "organization_id": None,
        "session_type": "identity_user",
        "role": "client",
    }


def _client() -> TestClient:
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_session] = FakeSession
    return TestClient(app)


def _profile(
    *,
    country_code: str,
    status: str = "active",
) -> SimpleNamespace:
    return SimpleNamespace(
        country_code=country_code,
        status=status,
    )


def _repository(monkeypatch, *, profile) -> AsyncMock:
    get_for_context = AsyncMock(return_value=profile)
    repository = SimpleNamespace(
        get_for_context=get_for_context,
    )
    monkeypatch.setattr(
        billing_router,
        "BillingProfileRepository",
        lambda session: repository,
    )
    return get_for_context


def test_checkout_options_show_tunisia_for_active_tunisian_profile(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "true")
    get_for_context = _repository(
        monkeypatch,
        profile=_profile(country_code="TN"),
    )
    client = _client()

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
        "billing_profile_exists": True,
        "billing_profile_status": "active",
    }
    get_for_context.assert_awaited_once_with(
        user_id=USER_ID,
        organization_id=None,
    )


def test_checkout_options_hide_tunisia_for_non_tunisian_profile(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "true")
    _repository(
        monkeypatch,
        profile=_profile(country_code="FR"),
    )
    client = _client()

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["eligible_channels"] == ["lemon_squeezy"]
    assert response.json()["show_tunisia_payment_option"] is False


def test_checkout_options_require_address_when_profile_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "true")
    _repository(monkeypatch, profile=None)
    client = _client()

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "address_country_code": None,
        "eligible_channels": ["lemon_squeezy"],
        "show_tunisia_payment_option": False,
        "customer_choice_allowed": False,
        "address_required": True,
        "billing_profile_exists": False,
        "billing_profile_status": None,
    }


def test_review_required_profile_never_exposes_tunisia(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "true")
    _repository(
        monkeypatch,
        profile=_profile(
            country_code="TN",
            status="review_required",
        ),
    )
    client = _client()

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["eligible_channels"] == ["lemon_squeezy"]
    assert response.json()["show_tunisia_payment_option"] is False
    assert response.json()["billing_profile_status"] == "review_required"


def test_checkout_options_reject_non_identity_session() -> None:
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "api-key-user",
        "user_id": "api-key-user",
        "session_type": "api_key",
    }
    app.dependency_overrides[get_session] = FakeSession
    client = TestClient(app)

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == ("billing_profile_requires_identity_session")


def test_checkout_options_hide_tunisia_when_feature_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MAESTRO_DIRECT_CHECKOUT_ENABLED", "false")
    _repository(
        monkeypatch,
        profile=_profile(country_code="TN"),
    )
    client = _client()

    try:
        response = client.get("/billing/checkout/options")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["address_country_code"] == "TN"
    assert response.json()["eligible_channels"] == ["lemon_squeezy"]
    assert response.json()["show_tunisia_payment_option"] is False
    assert response.json()["customer_choice_allowed"] is False
    assert response.json()["address_required"] is False
    assert response.json()["billing_profile_exists"] is True
    assert response.json()["billing_profile_status"] == "active"
