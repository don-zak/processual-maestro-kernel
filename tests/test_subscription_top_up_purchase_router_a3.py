from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from processual_api.admin_marketplace import subscription_top_up_purchase_router as purchase
from processual_api.admin_marketplace.lemon_squeezy_top_up_checkout import (
    CreateTopUpCheckoutResult,
)
from processual_api.admin_marketplace.subscription_top_up_order import (
    SubscriptionTopUpOrderResult,
)


def _enable_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", "true")
    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "ls-test-key")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "12345")
    monkeypatch.setenv("LEMONSQUEEZY_TOP_UP_VARIANT_ID", "98765")
    monkeypatch.setenv(
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
        "https://maestro.example/settings/billing",
    )


def test_purchase_is_fail_closed_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAESTRO_TOP_UP_PURCHASE_ENABLED", raising=False)

    assert purchase._purchase_enabled() is False


def test_provider_binding_is_server_side(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_provider(monkeypatch)

    config = purchase._required_provider_config()

    assert config.store_id == "12345"
    assert config.variant_id == "98765"
    assert config.success_url == "https://maestro.example/settings/billing"


def test_purchase_request_rejects_provider_control_fields() -> None:
    with pytest.raises(ValidationError):
        purchase.SubscriptionTopUpPurchaseRequest.model_validate(
            {
                "subscription_id": str(uuid.uuid4()),
                "quota_cycle_id": str(uuid.uuid4()),
                "requested_units": 10_000,
                "provider_variant_id": "1",
            }
        )


def test_order_id_is_stable_per_customer_and_idempotency_key() -> None:
    customer_ref = str(uuid.uuid4())

    first = purchase._deterministic_order_id(
        customer_ref=customer_ref,
        idempotency_key="checkout-1",
    )
    second = purchase._deterministic_order_id(
        customer_ref=customer_ref,
        idempotency_key="checkout-1",
    )
    different = purchase._deterministic_order_id(
        customer_ref=customer_ref,
        idempotency_key="checkout-2",
    )

    assert first == second
    assert first != different


def test_provider_config_fails_closed_when_top_up_variant_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_provider(monkeypatch)
    monkeypatch.delenv("LEMONSQUEEZY_TOP_UP_VARIANT_ID")

    with pytest.raises(HTTPException) as exc_info:
        purchase._required_provider_config()

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_purchase_wires_authoritative_order_to_server_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_provider(monkeypatch)
    customer_ref = str(uuid.uuid4())
    subscription_id = uuid.uuid4()
    cycle_id = uuid.uuid4()
    captured: dict[str, object] = {}

    def fake_order_factory(*, unit_of_work_factory):
        async def create(command):
            captured["order"] = command
            return SubscriptionTopUpOrderResult(
                order_id=command.order_id,
                plan_code="starter",
                quota_cycle_id=command.quota_cycle_id,
                requested_units=command.requested_units,
                bundle_count=1,
                total_price_usd="10.00",
                channel="lemon_squeezy",
                idempotent_replay=False,
                committed=True,
            )

        return create

    def fake_checkout_creator_factory(*, api_key: str):
        captured["api_key"] = api_key

        async def unused_creator(request):
            raise AssertionError("HTTP creator should be passed through, not called by this fake")

        return unused_creator

    def fake_checkout_factory(*, unit_of_work_factory, checkout_creator):
        async def create(command):
            captured["checkout"] = command
            return CreateTopUpCheckoutResult(
                order_id=command.order_id,
                checkout_id="a4cdd678-6ed6-42de-a8f7-951565604d62",
                url="https://app.lemonsqueezy.com/checkout/example",
                provider_variant_id=command.provider_variant_id,
                replayed=False,
                committed=True,
            )

        return create

    monkeypatch.setattr(
        purchase,
        "create_subscription_top_up_order_factory",
        fake_order_factory,
    )
    monkeypatch.setattr(
        purchase,
        "lemon_squeezy_http_checkout_creator_factory",
        fake_checkout_creator_factory,
    )
    monkeypatch.setattr(
        purchase,
        "create_lemon_squeezy_top_up_checkout_factory",
        fake_checkout_factory,
    )

    response = await purchase.purchase_subscription_top_up_endpoint(
        purchase.SubscriptionTopUpPurchaseRequest(
            subscription_id=subscription_id,
            quota_cycle_id=cycle_id,
            requested_units=10_000,
        ),
        current_user={"user_id": customer_ref},
        idempotency_key="top-up-request-1",
    )

    order_command = captured["order"]
    checkout_command = captured["checkout"]
    assert order_command.customer_ref == customer_ref
    assert order_command.subscription_id == subscription_id
    assert order_command.quota_cycle_id == cycle_id
    assert order_command.requested_units == 10_000
    assert checkout_command.customer_ref == customer_ref
    assert checkout_command.provider_variant_id == "98765"
    assert checkout_command.store_id == "12345"
    assert response.order_id == order_command.order_id
    assert response.replayed is False
