from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from processual_api.billing import router as billing
from processual_api.billing.canonical_checkout_resolution import (
    CanonicalCheckoutResolution,
)
from processual_api.billing.lemon_subscription_checkout import (
    CreateSubscriptionCheckoutResult,
    LemonSubscriptionCheckoutRequest,
    build_lemon_subscription_checkout_payload,
)


CUSTOMER_REF = "11111111-1111-4111-8111-111111111111"
USER_ID = "22222222-2222-4222-8222-222222222222"
SESSION_ID = "33333333-3333-4333-8333-333333333333"
OFFER_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
PLAN_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")
ORDER_ID = uuid.UUID("66666666-6666-4666-8666-666666666666")
ORDER_REF = "ord_authoritative_001"
CHECKOUT_ID = "77777777-7777-4777-8777-777777777777"


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return None


def _current_user() -> dict[str, str]:
    return {
        "organization_id": CUSTOMER_REF,
        "user_id": USER_ID,
        "session_id": SESSION_ID,
    }


def _resolution() -> CanonicalCheckoutResolution:
    return CanonicalCheckoutResolution(
        offer_id=OFFER_ID,
        offer_ref="pro_monthly",
        plan_id=PLAN_ID,
        display_name="Pro Monthly",
        billing_period="monthly",
        currency="USD",
        amount=Decimal("19.000"),
        provider_variant_id="123456",
    )


def test_subscription_checkout_payload_uses_current_lemon_json_api_contract() -> None:
    payload = build_lemon_subscription_checkout_payload(
        LemonSubscriptionCheckoutRequest(
            store_id="98765",
            variant_id="123456",
            customer_ref=CUSTOMER_REF,
            order_ref=ORDER_REF,
            offer_ref="pro_monthly",
            country_code="US",
            email="customer@example.test",
            success_url="https://example.test/billing/success",
        )
    )

    data = payload["data"]
    attributes = data["attributes"]
    custom = attributes["checkout_data"]["custom"]

    assert data["type"] == "checkouts"
    assert data["relationships"]["store"]["data"] == {
        "type": "stores",
        "id": "98765",
    }
    assert data["relationships"]["variant"]["data"] == {
        "type": "variants",
        "id": "123456",
    }
    assert attributes["product_options"]["enabled_variants"] == [123456]
    assert attributes["product_options"]["redirect_url"] == (
        "https://example.test/billing/success"
    )
    assert attributes["checkout_data"]["billing_address"] == {
        "country": "US"
    }
    assert custom == {
        "customer_ref": CUSTOMER_REF,
        "order_ref": ORDER_REF,
        "offer_ref": "pro_monthly",
    }
    assert "store_id" not in attributes
    assert "variant_id" not in attributes
    assert "custom_data" not in attributes


@pytest.mark.asyncio
async def test_checkout_requires_idempotency_before_any_authority_call(
    monkeypatch,
) -> None:
    resolver = AsyncMock()
    monkeypatch.setattr(billing, "resolve_canonical_checkout_in_session", resolver)

    with pytest.raises(HTTPException) as captured:
        await billing.create_checkout(
            body={"offer_ref": "pro_monthly"},
            current_user=_current_user(),
            idempotency_key=None,
            correlation_id=None,
        )

    assert captured.value.status_code == 400
    resolver.assert_not_awaited()


@pytest.mark.asyncio
async def test_checkout_uses_server_order_ref_and_authoritative_offer_snapshot(
    monkeypatch,
) -> None:
    resolution = _resolution()
    resolver = AsyncMock(return_value=resolution)
    monkeypatch.setattr(billing, "resolve_canonical_checkout_in_session", resolver)
    monkeypatch.setattr(billing, "get_session_factory", lambda: _SessionContext)

    order_prepare = AsyncMock(
        return_value=SimpleNamespace(
            order_id=ORDER_ID,
            order_ref=ORDER_REF,
        )
    )
    monkeypatch.setattr(
        billing,
        "build_lemon_checkout_order_authority",
        lambda: SimpleNamespace(prepare=order_prepare),
    )

    environment = {
        "LEMONSQUEEZY_API_KEY": "test-api-key",
        "LEMONSQUEEZY_STORE_ID": "98765",
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL": (
            "https://example.test/billing/success"
        ),
    }
    monkeypatch.setattr(
        billing,
        "_required_environment",
        lambda name: environment[name],
    )

    provider_create = AsyncMock(
        return_value=CreateSubscriptionCheckoutResult(
            order_id=ORDER_ID,
            order_ref=ORDER_REF,
            checkout_id=CHECKOUT_ID,
            url="https://example.test/provider-checkout",
            provider_variant_id="123456",
            committed=True,
        )
    )
    provider_creator = object()
    monkeypatch.setattr(
        billing,
        "lemon_subscription_http_checkout_creator_factory",
        lambda *, api_key: provider_creator,
    )
    checkout_factory = lambda **kwargs: provider_create
    monkeypatch.setattr(
        billing,
        "create_lemon_subscription_checkout_factory",
        checkout_factory,
    )

    response = await billing.create_checkout(
        body={
            "offer_ref": "pro_monthly",
            "email": "customer@example.test",
        },
        current_user=_current_user(),
        idempotency_key="checkout-idempotency-0001",
        correlation_id="corr-checkout-001",
    )

    assert response == {
        "url": "https://example.test/provider-checkout",
        "checkout_id": CHECKOUT_ID,
        "order_ref": ORDER_REF,
    }
    assert resolver.await_count == 2
    order_prepare.assert_awaited_once_with(
        actor_user_id=USER_ID,
        actor_session_id=SESSION_ID,
        customer_ref=CUSTOMER_REF,
        offer_id=OFFER_ID,
        offer_ref="pro_monthly",
        plan_id=PLAN_ID,
        billing_period="monthly",
        currency="USD",
        amount=Decimal("19.000"),
        display_name="Pro Monthly",
        correlation_id="corr-checkout-001",
        idempotency_key="checkout-idempotency-0001",
    )

    command = provider_create.await_args.args[0]
    assert command.order_id == ORDER_ID
    assert command.customer_ref == CUSTOMER_REF
    assert command.offer_ref == "pro_monthly"
    assert command.provider_variant_id == "123456"
    assert command.store_id == "98765"
    assert command.email == "customer@example.test"
