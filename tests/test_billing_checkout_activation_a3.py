from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

import processual_api.billing.router as billing_router
from processual_api.billing.canonical_checkout_gate import CanonicalCheckoutGateError
from processual_api.billing.canonical_checkout_resolution import (
    CanonicalCheckoutResolution,
)

CUSTOMER_REF = "00000000-0000-0000-0000-000000000001"


class _SessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _FakeResponse:
    def __init__(self, *, status_code: int = 201) -> None:
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return {
            "data": {
                "id": "checkout-001",
                "attributes": {"url": "https://checkout.example/001"},
            }
        }


def _install_session_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        billing_router,
        "get_session_factory",
        lambda: (lambda: _SessionContext()),
    )


def _install_checkout_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "lemon-api-key")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "12345")
    monkeypatch.setenv(
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
        "https://app.maestro.invalid/console",
    )
    monkeypatch.setenv(
        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL",
        "https://app.maestro.invalid/pricing",
    )


def test_checkout_uses_canonical_verified_variant_and_identity(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    resolver = AsyncMock(
        return_value=CanonicalCheckoutResolution(
            offer_ref="professional_monthly",
            provider_variant_id="67890",
        )
    )
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        resolver,
    )

    captured: dict[str, Any] = {}

    class _FakeClient:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            tb: object,
        ) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> _FakeResponse:
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    response = asyncio.run(
        billing_router.create_checkout(
            {
                "offer_ref": "PROFESSIONAL_MONTHLY",
                "email": "buyer@example.com",
            },
            {"sub": CUSTOMER_REF},
        )
    )

    resolver.assert_awaited_once()
    assert resolver.await_args.kwargs["offer_ref"] == "professional_monthly"
    attributes = captured["json"]["data"]["attributes"]
    assert attributes["store_id"] == 12345
    assert attributes["variant_id"] == 67890
    assert attributes["customer_email"] == "buyer@example.com"
    assert attributes["custom_data"] == {
        "customer_ref": CUSTOMER_REF,
        "offer_ref": "professional_monthly",
    }
    assert captured["url"] == "https://api.lemonsqueezy.com/v1/checkouts"
    assert captured["headers"]["Authorization"] == "Bearer lemon-api-key"
    assert response == {
        "url": "https://checkout.example/001",
        "checkout_id": "checkout-001",
    }


def test_checkout_missing_api_key_fails_before_provider_request(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.delenv("LEMONSQUEEZY_API_KEY")
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(
            return_value=CanonicalCheckoutResolution(
                offer_ref="starter_monthly",
                provider_variant_id="11111",
            )
        ),
    )

    client = AsyncMock()
    monkeypatch.setattr(httpx, "AsyncClient", client)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                {"sub": CUSTOMER_REF},
            )
        )

    assert captured.value.status_code == 503
    assert captured.value.detail == "Billing service is temporarily unavailable."
    client.assert_not_called()


def test_checkout_rejects_non_numeric_verified_variant(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(
            return_value=CanonicalCheckoutResolution(
                offer_ref="starter_monthly",
                provider_variant_id="variant-not-numeric",
            )
        ),
    )

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                {"sub": CUSTOMER_REF},
            )
        )

    assert captured.value.status_code == 503
    assert captured.value.detail == "Billing service is temporarily unavailable."


def test_checkout_provider_failure_is_fail_closed(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(
            return_value=CanonicalCheckoutResolution(
                offer_ref="starter_monthly",
                provider_variant_id="22222",
            )
        ),
    )

    class _FakeClient:
        def __init__(self, *, timeout: int) -> None:
            pass

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            tb: object,
        ) -> bool:
            return False

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> _FakeResponse:
            return _FakeResponse(status_code=422)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                {"sub": CUSTOMER_REF},
            )
        )

    assert captured.value.status_code == 502
    assert captured.value.detail == "Payment provider request failed."


def test_checkout_resolution_failure_does_not_contact_provider(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(
            side_effect=CanonicalCheckoutGateError("published_offer_required")
        ),
    )
    client = AsyncMock()
    monkeypatch.setattr(httpx, "AsyncClient", client)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                {"sub": CUSTOMER_REF},
            )
        )

    assert captured.value.status_code == 409
    assert captured.value.detail == "Checkout offer is not available."
    client.assert_not_called()
