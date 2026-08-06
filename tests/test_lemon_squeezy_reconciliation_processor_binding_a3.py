from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_reconciliation_gate import (
    LemonSqueezyReconciliationContext,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_processor import (
    process_lemon_squeezy_reconciliation_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)

NOW = datetime(2026, 8, 6, 11, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("00000000-0000-0000-0000-000000000101")
OFFER_ID = uuid.UUID("00000000-0000-0000-0000-000000000102")
SUBSCRIPTION_ID = uuid.UUID("00000000-0000-0000-0000-000000000103")


class InboxRepository:
    def __init__(self, inbox: object) -> None:
        self.inbox = inbox

    async def get_by_id(self, inbox_id: uuid.UUID, *, for_update: bool = False):
        return self.inbox if self.inbox.id == inbox_id else None


class DecisionRepository:
    def __init__(self) -> None:
        self.added: list[object] = []

    async def get_by_inbox_id(self, inbox_id: uuid.UUID, *, for_update: bool = False):
        return None

    def add(self, record: object) -> None:
        self.added.append(record)


class BindingRepository:
    def __init__(self, binding: object | None) -> None:
        self.binding = binding
        self.lookups: list[tuple[str, bool]] = []

    async def get_by_provider_order_id(
        self,
        provider_order_id: str,
        *,
        for_update: bool = False,
    ):
        self.lookups.append((provider_order_id, for_update))
        if self.binding is None:
            return None
        if self.binding.provider_order_id != provider_order_id:
            return None
        return self.binding


class SubscriptionRepository:
    def __init__(self, subscription: object | None) -> None:
        self.subscription = subscription
        self.lookups: list[tuple[uuid.UUID, bool]] = []

    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        self.lookups.append((subscription_id, for_update))
        if self.subscription is None:
            return None
        if self.subscription.id != subscription_id:
            return None
        return self.subscription


class FakeUnitOfWork:
    def __init__(
        self,
        inbox: object,
        binding: object | None = None,
        subscription: object | None = None,
    ) -> None:
        self.lemon_squeezy_webhook_inbox = InboxRepository(inbox)
        self.lemon_squeezy_reconciliation_decisions = DecisionRepository()
        self.lemon_squeezy_bindings = BindingRepository(binding or _binding())
        self.subscriptions = SubscriptionRepository(subscription or _subscription())
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _inbox(**overrides: object) -> SimpleNamespace:
    values = {
        "id": uuid.uuid4(),
        "event_identity_hash": "a" * 64,
        "customer_ref": "customer_001",
        "order_ref": "order_001",
        "offer_ref": "starter_monthly",
        "event_name": "subscription_updated",
        "resource_type": "subscriptions",
        "external_resource_id": "9001",
        "test_mode": False,
        "processing_status": "received",
        "attempt_count": 0,
        "received_at": NOW,
        "claimed_at": None,
        "processed_at": None,
        "rejected_at": None,
        "last_error_code": None,
        "evidence_schema_version": 1,
        "provider_customer_id": "7001",
        "provider_order_id": "8001",
        "provider_subscription_id": "9001",
        "variant_id": "6001",
        "currency": None,
        "total_amount": None,
        "provider_status": "active",
        "provider_effective_at": NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _binding(**overrides: object) -> SimpleNamespace:
    values = {
        "customer_ref": "customer_001",
        "order_id": ORDER_ID,
        "offer_id": OFFER_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "provider_customer_id": "7001",
        "provider_order_id": "8001",
        "provider_subscription_id": None,
        "variant_id": "6001",
        "last_provider_effective_at": NOW - timedelta(hours=1),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _subscription(**overrides: object) -> SimpleNamespace:
    values = {
        "id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "order_id": ORDER_ID,
        "offer_id": OFFER_ID,
        "status": "pending",
        "starts_at": None,
        "ends_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _context(**overrides: object) -> LemonSqueezyReconciliationContext:
    values = {
        "expected_customer_ref": "customer_001",
        "expected_order_ref": "order_001",
        "expected_offer_ref": "starter_monthly",
        "order_sales_channel": "lemon_squeezy",
        "offer_sales_channel": "lemon_squeezy",
        "production_mode": True,
        "expected_provider_customer_id": "7001",
        "expected_provider_order_id": "8001",
        "expected_provider_subscription_id": "9001",
        "expected_variant_id": "6001",
        "latest_provider_effective_at": NOW - timedelta(hours=1),
    }
    values.update(overrides)
    return LemonSqueezyReconciliationContext(**values)


@pytest.mark.asyncio
async def test_context_loader_receives_active_unit_of_work_and_locked_inbox() -> None:
    inbox = _inbox()
    binding = _binding()
    subscription = _subscription()
    uow = FakeUnitOfWork(inbox, binding, subscription)
    observed: list[tuple[object, object]] = []

    async def loader(active_uow: object, locked_inbox: object):
        observed.append((active_uow, locked_inbox))
        return _context()

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )

    record = await process(inbox_id=inbox.id, decided_at=NOW)

    assert observed == [(uow, inbox)]
    assert record.action == "reconcile"
    assert uow.lemon_squeezy_bindings.lookups == [("8001", True)]
    assert uow.subscriptions.lookups == [(SUBSCRIPTION_ID, True)]
    assert binding.provider_subscription_id == "9001"
    assert binding.last_provider_effective_at == NOW
    assert subscription.status == "active"
    assert subscription.starts_at == NOW
    assert uow.committed is True


@pytest.mark.asyncio
async def test_conflicting_context_binding_is_rejected_without_commit() -> None:
    inbox = _inbox()
    uow = FakeUnitOfWork(inbox)

    async def loader(active_uow: object, locked_inbox: object):
        return _context(expected_customer_ref="customer_999")

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )

    with pytest.raises(
        LemonSqueezyWebhookError,
        match="context conflicts with inbox binding",
    ):
        await process(inbox_id=inbox.id, decided_at=NOW)

    assert uow.committed is False
    assert uow.lemon_squeezy_reconciliation_decisions.added == []


@pytest.mark.asyncio
async def test_missing_authoritative_binding_rejects_without_commit() -> None:
    inbox = _inbox()
    uow = FakeUnitOfWork(inbox)
    uow.lemon_squeezy_bindings = BindingRepository(None)

    async def loader(active_uow: object, locked_inbox: object):
        return _context()

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )

    with pytest.raises(LemonSqueezyWebhookError, match="binding was not found"):
        await process(inbox_id=inbox.id, decided_at=NOW)

    assert uow.committed is False


@pytest.mark.asyncio
async def test_binding_subscription_conflict_rejects_without_commit() -> None:
    inbox = _inbox()
    binding = _binding(provider_subscription_id="9999")
    uow = FakeUnitOfWork(inbox, binding)

    async def loader(active_uow: object, locked_inbox: object):
        return _context()

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )

    with pytest.raises(LemonSqueezyWebhookError, match="subscription conflicts"):
        await process(inbox_id=inbox.id, decided_at=NOW)

    assert binding.provider_subscription_id == "9999"
    assert uow.committed is False


@pytest.mark.asyncio
async def test_binding_watermark_cannot_move_backwards() -> None:
    inbox = _inbox(provider_effective_at=NOW - timedelta(hours=2))
    binding = _binding(last_provider_effective_at=NOW)
    uow = FakeUnitOfWork(inbox, binding)

    async def loader(active_uow: object, locked_inbox: object):
        return _context(latest_provider_effective_at=None)

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )

    with pytest.raises(LemonSqueezyWebhookError, match="older than binding watermark"):
        await process(inbox_id=inbox.id, decided_at=NOW)

    assert binding.last_provider_effective_at == NOW
    assert uow.committed is False


@pytest.mark.asyncio
async def test_requires_review_does_not_mutate_binding() -> None:
    inbox = _inbox(provider_customer_id="wrong")
    binding = _binding()
    subscription = _subscription()
    original_watermark = binding.last_provider_effective_at
    uow = FakeUnitOfWork(inbox, binding, subscription)

    async def loader(active_uow: object, locked_inbox: object):
        return _context()

    process = process_lemon_squeezy_reconciliation_factory(
        uow_factory=lambda: uow,
        context_loader=loader,
    )

    record = await process(inbox_id=inbox.id, decided_at=NOW)

    assert record.action == "requires_review"
    assert uow.lemon_squeezy_bindings.lookups == []
    assert uow.subscriptions.lookups == []
    assert binding.provider_subscription_id is None
    assert binding.last_provider_effective_at == original_watermark
    assert subscription.status == "pending"
    assert uow.committed is True
