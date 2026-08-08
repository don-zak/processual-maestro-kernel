from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_top_up_processor import TOP_UP_OFFER_REF
from processual_api.admin_marketplace.lemon_squeezy_top_up_refund_processor import (
    process_lemon_squeezy_top_up_refund_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import LemonSqueezyWebhookError

NOW = datetime(2026, 8, 26, tzinfo=UTC)
INBOX_ID = uuid.uuid4()
ORDER_ID = uuid.uuid4()
GRANT_ID = uuid.uuid4()
SUBSCRIPTION_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()
VARIANT_ID = "9001"
PROVIDER_ORDER_ID = "7001"


class ByIdRepo:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id, *, for_update: bool = False):
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class GrantRepo:
    def __init__(self, grant: object | None) -> None:
        self.grant = grant

    async def get_by_order_id(self, order_id, *, for_update: bool = False):
        if self.grant is None or self.grant.order_id != order_id:
            return None
        return self.grant


class ReversalRepo:
    def __init__(self) -> None:
        self.reversal = None

    async def get_by_provider_event_ref(self, provider_event_ref: str, *, for_update: bool = False):
        if self.reversal is None or self.reversal.provider_event_ref != provider_event_ref:
            return None
        return self.reversal

    async def get_by_grant_id(self, grant_id, *, for_update: bool = False):
        if self.reversal is None or self.reversal.grant_id != grant_id:
            return None
        return self.reversal

    def add(self, reversal: object) -> None:
        self.reversal = reversal


class FakeUow:
    def __init__(self, *, inbox: object, used_units: int = 8_000) -> None:
        self.inbox = inbox
        self.order = SimpleNamespace(
            id=ORDER_ID,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            customer_ref="customer_001",
            channel="lemon_squeezy",
            provider_variant_id=VARIANT_ID,
            state="granted",
        )
        self.grant = SimpleNamespace(
            id=GRANT_ID,
            order_id=ORDER_ID,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            customer_ref="customer_001",
            units=10_000,
        )
        self.cycle = SimpleNamespace(
            id=CYCLE_ID,
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer_001",
            base_limit_units=10_000,
            spendable_rollover_units=0,
            top_up_units=10_000,
            used_units=used_units,
            version=1,
        )
        self.lemon_squeezy_webhook_inbox = ByIdRepo(self.inbox)
        self.top_up_orders = ByIdRepo(self.order)
        self.subscription_top_up_grants = GrantRepo(self.grant)
        self.subscription_quota_cycles = ByIdRepo(self.cycle)
        self.subscription_top_up_reversals = ReversalRepo()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _inbox(**overrides: object) -> SimpleNamespace:
    values = {
        "id": INBOX_ID,
        "order_ref": str(ORDER_ID),
        "offer_ref": TOP_UP_OFFER_REF,
        "customer_ref": "customer_001",
        "event_name": "order_refunded",
        "resource_type": "orders",
        "external_resource_id": PROVIDER_ORDER_ID,
        "provider_order_id": PROVIDER_ORDER_ID,
        "provider_subscription_id": None,
        "provider_status": "refunded",
        "variant_id": VARIANT_ID,
        "currency": "USD",
        "subtotal_amount": "1000",
        "total_amount": "1200",
        "refunded_amount": "1200",
        "payload_digest": "c" * 64,
        "processing_status": "received",
        "attempt_count": 0,
        "claimed_at": None,
        "processed_at": None,
        "rejected_at": None,
        "last_error_code": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_full_refund_reverses_available_top_up_balance() -> None:
    uow = FakeUow(inbox=_inbox(), used_units=8_000)
    process = process_lemon_squeezy_top_up_refund_factory(uow_factory=lambda: uow)

    result = await process(inbox_id=INBOX_ID, processed_at=NOW)

    assert result.outcome == "reversed"
    assert result.reversal_id is not None
    assert uow.cycle.top_up_units == 0
    assert uow.cycle.version == 2
    assert uow.inbox.processing_status == "processed"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_partial_refund_is_manual_review_without_balance_change() -> None:
    uow = FakeUow(
        inbox=_inbox(provider_status="partial_refund", refunded_amount="600"),
        used_units=8_000,
    )
    process = process_lemon_squeezy_top_up_refund_factory(uow_factory=lambda: uow)

    result = await process(inbox_id=INBOX_ID, processed_at=NOW)

    assert result.outcome == "manual_review"
    assert result.reversal_id is None
    assert uow.cycle.top_up_units == 10_000
    assert uow.subscription_top_up_reversals.reversal is None
    assert uow.inbox.processing_status == "processed"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_full_refund_is_manual_review_if_top_up_units_were_consumed() -> None:
    uow = FakeUow(inbox=_inbox(), used_units=15_000)
    process = process_lemon_squeezy_top_up_refund_factory(uow_factory=lambda: uow)

    result = await process(inbox_id=INBOX_ID, processed_at=NOW)

    assert result.outcome == "manual_review"
    assert result.reversal_id is not None
    assert uow.cycle.top_up_units == 10_000
    assert uow.subscription_top_up_reversals.reversal.reason_code == "units_already_consumed"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_refund_status_amount_conflict_fails_closed() -> None:
    uow = FakeUow(
        inbox=_inbox(provider_status="refunded", refunded_amount="600"),
        used_units=8_000,
    )
    process = process_lemon_squeezy_top_up_refund_factory(uow_factory=lambda: uow)

    with pytest.raises(LemonSqueezyWebhookError, match="status conflicts"):
        await process(inbox_id=INBOX_ID, processed_at=NOW)

    assert uow.cycle.top_up_units == 10_000
    assert uow.subscription_top_up_reversals.reversal is None
    assert uow.commit_count == 0
