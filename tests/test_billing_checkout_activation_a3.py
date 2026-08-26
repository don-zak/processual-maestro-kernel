from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import processual_api.billing.router as billing_router
from processual_api.billing.canonical_checkout_gate import CanonicalCheckoutGateError
from processual_api.billing.canonical_checkout_resolution import CanonicalCheckoutResolution
from processual_api.billing.lemon_subscription_checkout import LemonSubscriptionCheckoutError

CUSTOMER_REF = "00000000-0000-0000-0000-000000000001"
OFFER_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
PLAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000102")
ORDER_ID = uuid.UUID("00000000-0000-0000-0000-000000000103")
IDEMPOTENCY_KEY = "checkout-request-0001"


class _SessionContext:
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


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


def _resolution(
    *,
    offer_ref: str = "starter_monthly",
    provider_variant_id: str = "67890",
) -> CanonicalCheckoutResolution:
    return CanonicalCheckoutResolution(
        offer_id=OFFER_ID,
        offer_ref=offer_ref,
        plan_id=PLAN_ID,
        display_name="Starter Monthly",
        billing_period="monthly",
        currency="USD",
        amount=Decimal("49.00"),
        provider_variant_id=provider_variant_id,
    )


def _current_user() -> dict[str, str]:
    return {
        "sub": CUSTOMER_REF,
        "user_id": CUSTOMER_REF,
        "session_id": "session-checkout-001",
    }


def _install_order_authority(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    prepare = AsyncMock(
        return_value=SimpleNamespace(
            order_id=ORDER_ID,
            order_ref="ord_checkout_001",
        )
    )
    monkeypatch.setattr(
        billing_router,
        "build_lemon_checkout_order_authority",
        lambda: SimpleNamespace(prepare=prepare),
    )
    return prepare


def _install_provider_checkout(
    monkeypatch: pytest.MonkeyPatch,
    *,
    error: Exception | None = None,
) -> AsyncMock:
    create = AsyncMock(
        side_effect=error,
        return_value=None
        if error is not None
        else SimpleNamespace(
            url="https://checkout.example/001",
            checkout_id="checkout-001",
            order_ref="ord_checkout_001",
        ),
    )
    monkeypatch.setattr(
        billing_router,
        "create_lemon_subscription_checkout_factory",
        lambda **kwargs: create,
    )
    monkeypatch.setattr(
        billing_router,
        "lemon_subscription_http_checkout_creator_factory",
        lambda **kwargs: object(),
    )
    return create


def test_checkout_uses_canonical_authority_order_and_identity(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    resolution = _resolution()
    resolver = AsyncMock(return_value=resolution)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        resolver,
    )
    prepare = _install_order_authority(monkeypatch)
    create = _install_provider_checkout(monkeypatch)

    response = asyncio.run(
        billing_router.create_checkout(
            {"offer_ref": "STARTER_MONTHLY", "email": "buyer@example.com"},
            _current_user(),
            idempotency_key=IDEMPOTENCY_KEY,
            correlation_id="corr-checkout-001",
        )
    )

    assert resolver.await_count == 2
    assert resolver.await_args_list[0].kwargs["offer_ref"] == "starter_monthly"
    prepare.assert_awaited_once()
    prepared = prepare.await_args.kwargs
    assert prepared["actor_user_id"] == CUSTOMER_REF
    assert prepared["actor_session_id"] == "session-checkout-001"
    assert prepared["customer_ref"] == CUSTOMER_REF
    assert prepared["offer_id"] == OFFER_ID
    assert prepared["plan_id"] == PLAN_ID
    assert prepared["billing_period"] == "monthly"
    assert prepared["currency"] == "USD"
    assert prepared["amount"] == Decimal("49.00")
    assert prepared["idempotency_key"] == IDEMPOTENCY_KEY
    create.assert_awaited_once()
    command = create.await_args.args[0]
    assert command.order_id == ORDER_ID
    assert command.customer_ref == CUSTOMER_REF
    assert command.offer_ref == "starter_monthly"
    assert command.provider_variant_id == "67890"
    assert command.store_id == "12345"
    assert command.email == "buyer@example.com"
    assert response == {
        "url": "https://checkout.example/001",
        "checkout_id": "checkout-001",
        "order_ref": "ord_checkout_001",
    }


def test_checkout_missing_api_key_fails_before_order_or_provider(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.delenv("LEMONSQUEEZY_API_KEY")
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(return_value=_resolution()),
    )
    prepare = _install_order_authority(monkeypatch)
    create = _install_provider_checkout(monkeypatch)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                _current_user(),
                idempotency_key=IDEMPOTENCY_KEY,
            )
        )

    assert captured.value.status_code == 503
    assert captured.value.detail == "Billing service is temporarily unavailable."
    prepare.assert_not_awaited()
    create.assert_not_awaited()


def test_checkout_rejects_non_numeric_verified_variant_before_order(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(return_value=_resolution(provider_variant_id="variant-not-numeric")),
    )
    prepare = _install_order_authority(monkeypatch)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                _current_user(),
                idempotency_key=IDEMPOTENCY_KEY,
            )
        )

    assert captured.value.status_code == 503
    assert captured.value.detail == "Billing service is temporarily unavailable."
    prepare.assert_not_awaited()


def test_checkout_provider_failure_is_fail_closed_after_durable_order(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(return_value=_resolution()),
    )
    prepare = _install_order_authority(monkeypatch)
    create = _install_provider_checkout(
        monkeypatch,
        error=LemonSubscriptionCheckoutError(
            "payment provider checkout creation outcome is uncertain."
        ),
    )

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                _current_user(),
                idempotency_key=IDEMPOTENCY_KEY,
            )
        )

    assert captured.value.status_code == 503
    assert "provider" in str(captured.value.detail)
    prepare.assert_awaited_once()
    create.assert_awaited_once()


def test_checkout_resolution_failure_does_not_create_order_or_contact_provider(monkeypatch) -> None:
    _install_session_factory(monkeypatch)
    _install_checkout_environment(monkeypatch)
    monkeypatch.setattr(
        billing_router,
        "resolve_canonical_checkout_in_session",
        AsyncMock(side_effect=CanonicalCheckoutGateError("published_offer_required")),
    )
    prepare = _install_order_authority(monkeypatch)
    create = _install_provider_checkout(monkeypatch)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(
            billing_router.create_checkout(
                {"offer_ref": "starter_monthly"},
                _current_user(),
                idempotency_key=IDEMPOTENCY_KEY,
            )
        )

    assert captured.value.status_code == 409
    assert captured.value.detail == "Checkout offer is not available."
    prepare.assert_not_awaited()
    create.assert_not_awaited()
