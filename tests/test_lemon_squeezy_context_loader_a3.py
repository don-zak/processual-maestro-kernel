from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_context_loader import (
    lemon_squeezy_reconciliation_context_loader_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)

NOW = datetime(2026, 8, 6, 11, 30, tzinfo=UTC)


class SingleRepository:
    def __init__(self, value: object) -> None:
        self.value = value
        self.calls: list[tuple[object, bool]] = []

    async def get_by_ref(self, value: object, *, for_update: bool = False):
        self.calls.append((value, for_update))
        return self.value

    async def get_by_id(self, value: object, *, for_update: bool = False):
        self.calls.append((value, for_update))
        return self.value

    async def get_active_by_customer_ref(
        self,
        value: object,
        *,
        for_update: bool = False,
    ):
        self.calls.append((value, for_update))
        return self.value


class BindingRepository:
    def __init__(self, binding: object, customer_owner: object) -> None:
        self.binding = binding
        self.customer_owner = customer_owner
        self.provider_owner = customer_owner
        self.subscription_owner = binding
        self.calls: list[tuple[str, object, bool]] = []

    async def get_customer_binding_by_customer_ref(
        self,
        value: object,
        *,
        for_update: bool = False,
    ):
        self.calls.append(("customer_ref", value, for_update))
        return self.customer_owner

    async def get_customer_binding_by_provider_customer_id(
        self,
        value: object,
        *,
        for_update: bool = False,
    ):
        self.calls.append(("provider_customer", value, for_update))
        return self.provider_owner

    async def get_by_order_id(self, value: object, *, for_update: bool = False):
        self.calls.append(("order", value, for_update))
        return self.binding

    async def get_by_provider_subscription_id(
        self,
        value: object,
        *,
        for_update: bool = False,
    ):
        self.calls.append(("subscription", value, for_update))
        return self.subscription_owner


def _fixtures():
    order_id = uuid.uuid4()
    offer_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    binding_id = uuid.uuid4()
    customer_binding_id = uuid.uuid4()
    order = SimpleNamespace(
        id=order_id,
        order_ref="order_001",
        customer_ref="customer_001",
        offer_id=offer_id,
        selected_channel="lemon_squeezy",
        billing_period="monthly",
    )
    offer = SimpleNamespace(
        id=offer_id,
        offer_code="starter_monthly",
        sales_channel="lemon_squeezy",
        billing_period="monthly",
    )
    subscription = SimpleNamespace(
        id=subscription_id,
        order_id=order_id,
        offer_id=offer_id,
    )
    customer_owner = SimpleNamespace(
        id=customer_binding_id,
        customer_ref="customer_001",
        provider_customer_id="501",
    )
    binding = SimpleNamespace(
        id=binding_id,
        customer_ref="customer_001",
        order_id=order_id,
        offer_id=offer_id,
        subscription_id=subscription_id,
        provider_customer_id="501",
        provider_order_id="801",
        provider_subscription_id="9001",
        variant_id="301",
        currency="USD",
        total_amount="1000",
        last_provider_effective_at=NOW,
    )
    inbox = SimpleNamespace(
        order_ref="order_001",
        customer_ref="customer_001",
        offer_ref="starter_monthly",
        provider_customer_id="501",
        provider_subscription_id="9001",
        test_mode=False,
    )
    bindings = BindingRepository(binding, customer_owner)
    uow = SimpleNamespace(
        orders=SingleRepository(order),
        offers=SingleRepository(offer),
        subscriptions=SingleRepository(subscription),
        lemon_squeezy_bindings=bindings,
    )
    return uow, inbox, binding


@pytest.mark.asyncio
async def test_loader_builds_context_from_locked_authoritative_records() -> None:
    uow, inbox, _ = _fixtures()
    loader = lemon_squeezy_reconciliation_context_loader_factory(
        production_mode=True
    )

    context = await loader(uow, inbox)

    assert context.production_mode is True
    assert context.expected_provider_customer_id == "501"
    assert context.expected_provider_order_id == "801"
    assert context.expected_provider_subscription_id == "9001"
    assert context.expected_variant_id == "301"
    assert context.expected_currency == "USD"
    assert context.expected_total_amount == "1000"
    assert context.latest_provider_effective_at == NOW
    assert all(call[1] is True for call in uow.orders.calls)
    assert all(call[1] is True for call in uow.offers.calls)
    assert all(call[1] is True for call in uow.subscriptions.calls)
    assert all(call[2] is True for call in uow.lemon_squeezy_bindings.calls)


@pytest.mark.asyncio
async def test_loader_rejects_cross_customer_provider_owner() -> None:
    uow, inbox, binding = _fixtures()
    uow.lemon_squeezy_bindings.provider_owner = SimpleNamespace(
        id=uuid.uuid4(),
        customer_ref="customer_999",
        provider_customer_id="501",
    )
    loader = lemon_squeezy_reconciliation_context_loader_factory(
        production_mode=True
    )

    with pytest.raises(
        LemonSqueezyWebhookError,
        match="conflicting ownership",
    ):
        await loader(uow, inbox)

    assert binding.customer_ref == "customer_001"


@pytest.mark.asyncio
async def test_loader_rejects_active_subscription_for_another_order() -> None:
    uow, inbox, _ = _fixtures()
    uow.subscriptions.value = SimpleNamespace(
        id=uuid.uuid4(),
        order_id=uuid.uuid4(),
        offer_id=uow.offers.value.id,
    )
    loader = lemon_squeezy_reconciliation_context_loader_factory(
        production_mode=True
    )

    with pytest.raises(
        LemonSqueezyWebhookError,
        match="active subscription for another order",
    ):
        await loader(uow, inbox)


@pytest.mark.asyncio
async def test_loader_uses_trusted_environment_mode_not_webhook_mode() -> None:
    uow, inbox, _ = _fixtures()
    inbox.test_mode = False
    loader = lemon_squeezy_reconciliation_context_loader_factory(
        production_mode=False
    )

    context = await loader(uow, inbox)

    assert context.production_mode is False
