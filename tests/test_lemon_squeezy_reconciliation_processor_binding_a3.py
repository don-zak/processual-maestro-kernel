from __future__ import annotations

import uuid
from datetime import UTC, datetime
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


class FakeUnitOfWork:
    def __init__(self, inbox: object) -> None:
        self.lemon_squeezy_webhook_inbox = InboxRepository(inbox)
        self.lemon_squeezy_reconciliation_decisions = DecisionRepository()
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _inbox() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        event_identity_hash="a" * 64,
        customer_ref="customer_001",
        order_ref="order_001",
        offer_ref="starter_monthly",
        event_name="subscription_updated",
        resource_type="subscriptions",
        external_resource_id="9001",
        test_mode=False,
        processing_status="received",
        attempt_count=0,
        received_at=NOW,
        claimed_at=None,
        processed_at=None,
        rejected_at=None,
        last_error_code=None,
        evidence_schema_version=1,
        provider_customer_id="7001",
        provider_order_id="8001",
        provider_subscription_id="9001",
        variant_id="6001",
        currency=None,
        total_amount=None,
        provider_status="active",
        provider_effective_at=NOW,
    )


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
    }
    values.update(overrides)
    return LemonSqueezyReconciliationContext(**values)


@pytest.mark.asyncio
async def test_context_loader_receives_active_unit_of_work_and_locked_inbox() -> None:
    inbox = _inbox()
    uow = FakeUnitOfWork(inbox)
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
