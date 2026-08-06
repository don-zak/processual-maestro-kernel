from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    AdminMarketLemonSqueezyBinding,
    AdminMarketLemonSqueezyCustomerBinding,
)
from processual_api.admin_marketplace.lemon_squeezy_binding_service import (
    LemonSqueezyBindingCommand,
    LemonSqueezyBindingConflictError,
    bind_lemon_squeezy_order_factory,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
)


class FakeBindings:
    def __init__(self) -> None:
        self.customer_owner = None
        self.provider_owner = None
        self.existing = None
        self.added_customer = None
        self.added_binding = None

    async def get_customer_binding_by_customer_ref(self, customer_ref, *, for_update=False):
        assert for_update is True
        return self.customer_owner

    async def get_customer_binding_by_provider_customer_id(
        self,
        provider_customer_id,
        *,
        for_update=False,
    ):
        assert for_update is True
        return self.provider_owner

    async def get_by_order_id(self, order_id, *, for_update=False):
        assert for_update is True
        return self.existing

    def add_customer_binding(self, binding):
        self.added_customer = binding

    def add(self, binding):
        self.added_binding = binding


class FakeUow:
    def __init__(self, bindings: FakeBindings, *, commit_error: Exception | None = None) -> None:
        self.lemon_squeezy_bindings = bindings
        self.commit_error = commit_error
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def commit(self):
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error


def _command() -> LemonSqueezyBindingCommand:
    return LemonSqueezyBindingCommand(
        customer_ref="customer_001",
        order_id=uuid.uuid4(),
        offer_id=uuid.uuid4(),
        provider_customer_id="5001",
        provider_order_id="6001",
        provider_subscription_id="9001",
        variant_id="8001",
        currency="usd",
        total_amount="1000",
    )


@pytest.mark.asyncio
async def test_creates_customer_owner_and_order_binding() -> None:
    bindings = FakeBindings()
    uow = FakeUow(bindings)
    bind = bind_lemon_squeezy_order_factory(unit_of_work_factory=lambda: uow)

    result = await bind(_command())

    assert isinstance(bindings.added_customer, AdminMarketLemonSqueezyCustomerBinding)
    assert isinstance(bindings.added_binding, AdminMarketLemonSqueezyBinding)
    assert result is bindings.added_binding
    assert result.currency == "USD"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_exact_existing_binding_is_idempotent_without_commit() -> None:
    command = _command()
    bindings = FakeBindings()
    bindings.customer_owner = AdminMarketLemonSqueezyCustomerBinding(
        customer_ref=command.customer_ref,
        provider_customer_id=command.provider_customer_id,
    )
    bindings.provider_owner = bindings.customer_owner
    bindings.existing = AdminMarketLemonSqueezyBinding(
        customer_ref=command.customer_ref,
        order_id=command.order_id,
        offer_id=command.offer_id,
        subscription_id=command.subscription_id,
        provider_customer_id=command.provider_customer_id,
        provider_order_id=command.provider_order_id,
        provider_subscription_id=command.provider_subscription_id,
        variant_id=command.variant_id,
        currency="USD",
        total_amount=command.total_amount,
    )
    uow = FakeUow(bindings)
    bind = bind_lemon_squeezy_order_factory(unit_of_work_factory=lambda: uow)

    result = await bind(command)

    assert result is bindings.existing
    assert bindings.added_customer is None
    assert bindings.added_binding is None
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_provider_customer_cross_owner_is_rejected() -> None:
    command = _command()
    bindings = FakeBindings()
    bindings.provider_owner = AdminMarketLemonSqueezyCustomerBinding(
        customer_ref="customer_999",
        provider_customer_id=command.provider_customer_id,
    )
    bind = bind_lemon_squeezy_order_factory(
        unit_of_work_factory=lambda: FakeUow(bindings)
    )

    with pytest.raises(LemonSqueezyBindingConflictError):
        await bind(command)


@pytest.mark.asyncio
async def test_existing_order_with_different_binding_is_rejected() -> None:
    command = _command()
    bindings = FakeBindings()
    bindings.customer_owner = AdminMarketLemonSqueezyCustomerBinding(
        customer_ref=command.customer_ref,
        provider_customer_id=command.provider_customer_id,
    )
    bindings.provider_owner = bindings.customer_owner
    bindings.existing = SimpleNamespace(
        customer_ref=command.customer_ref,
        offer_id=uuid.uuid4(),
        subscription_id=None,
        provider_customer_id=command.provider_customer_id,
        provider_order_id=command.provider_order_id,
        provider_subscription_id=command.provider_subscription_id,
        variant_id=command.variant_id,
        currency="USD",
        total_amount=command.total_amount,
    )
    bind = bind_lemon_squeezy_order_factory(
        unit_of_work_factory=lambda: FakeUow(bindings)
    )

    with pytest.raises(LemonSqueezyBindingConflictError):
        await bind(command)


@pytest.mark.asyncio
async def test_persistence_conflict_is_translated_to_domain_conflict() -> None:
    bindings = FakeBindings()
    uow = FakeUow(
        bindings,
        commit_error=AdminMarketplaceConflictError("duplicate"),
    )
    bind = bind_lemon_squeezy_order_factory(unit_of_work_factory=lambda: uow)

    with pytest.raises(LemonSqueezyBindingConflictError):
        await bind(_command())
