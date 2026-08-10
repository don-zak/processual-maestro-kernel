from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_top_up_processor import (
    TOP_UP_OFFER_REF,
    process_lemon_squeezy_top_up_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import LemonSqueezyWebhookError
from processual_api.billing.commercial_quota_top_up_contracts import quote_top_up
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_CATALOG_VERSION

START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 9, 1, tzinfo=UTC)
INBOX_ID = uuid.uuid4()
ORDER_ID = uuid.uuid4()
SUBSCRIPTION_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
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


class PaymentRepo:
    def __init__(self) -> None:
        self.payment = None

    async def get_by_provider_reference(self, provider_reference: str):
        if self.payment is None or self.payment.provider_reference != provider_reference:
            return None
        return self.payment

    def add(self, payment: object) -> None:
        self.payment = payment


class GrantRepo:
    def __init__(self) -> None:
        self.grant = None

    async def get_by_order_id(self, order_id, *, for_update: bool = False):
        if self.grant is None or self.grant.order_id != order_id:
            return None
        return self.grant

    async def get_by_idempotency_key(self, key: str, *, for_update: bool = False):
        if self.grant is None or self.grant.grant_idempotency_key != key:
            return None
        return self.grant

    def add(self, grant: object) -> None:
        self.grant = grant


class FakeUow:
    def __init__(self, *, inbox: object, order: object, cycle: object) -> None:
        self.lemon_squeezy_webhook_inbox = ByIdRepo(inbox)
        self.top_up_orders = ByIdRepo(order)
        self.subscriptions = ByIdRepo(
            SimpleNamespace(
                id=SUBSCRIPTION_ID,
                customer_ref="customer_001",
                plan_id=PLAN_ID,
                status="active",
            )
        )
        self.plans = ByIdRepo(SimpleNamespace(id=PLAN_ID, plan_code="starter"))
        self.subscription_quota_cycles = ByIdRepo(cycle)
        self.top_up_payments = PaymentRepo()
        self.subscription_top_up_grants = GrantRepo()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


def _order(**overrides: object) -> SimpleNamespace:
    quote = quote_top_up("starter", 10_000)
    values = {
        "id": ORDER_ID,
        "customer_ref": "customer_001",
        "subscription_id": SUBSCRIPTION_ID,
        "quota_cycle_id": CYCLE_ID,
        "plan_code": "starter",
        "plan_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
        "requested_units": quote.total_units,
        "bundle_count": quote.bundle_count,
        "total_price_usd": quote.total_price_usd,
        "settlement_currency": "USD",
        "settlement_amount": quote.total_price_usd,
        "channel": "lemon_squeezy",
        "provider_variant_id": VARIANT_ID,
        "provider_checkout_id": None,
        "checkout_creation_status": "uncertain",
        "state": "awaiting_payment",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _cycle(**overrides: object) -> SimpleNamespace:
    values = {
        "id": CYCLE_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "metric_code": "credits",
        "period_start": START,
        "period_end": END,
        "plan_code": "starter",
        "plan_catalog_version": PLAN_FULFILLMENT_CATALOG_VERSION,
        "base_limit_units": 10_000,
        "used_units": 8_000,
        "top_up_units": 0,
        "version": 1,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _inbox() -> SimpleNamespace:
    quote = quote_top_up("starter", 10_000)
    subtotal_cents = int(quote.total_price_usd * 100)
    return SimpleNamespace(
        id=INBOX_ID,
        order_ref=str(ORDER_ID),
        offer_ref=TOP_UP_OFFER_REF,
        customer_ref="customer_001",
        event_name="order_created",
        resource_type="orders",
        external_resource_id=PROVIDER_ORDER_ID,
        provider_order_id=PROVIDER_ORDER_ID,
        provider_subscription_id=None,
        provider_status="paid",
        variant_id=VARIANT_ID,
        currency="USD",
        subtotal_amount=str(subtotal_cents),
        total_amount=str(subtotal_cents),
        payload_digest="b" * 64,
        processing_status="received",
        attempt_count=0,
        claimed_at=None,
        processed_at=None,
        rejected_at=None,
        last_error_code=None,
    )


@pytest.mark.asyncio
async def test_paid_webhook_can_settle_when_checkout_response_was_uncertain() -> None:
    inbox = _inbox()
    order = _order(checkout_creation_status="uncertain")
    cycle = _cycle()
    uow = FakeUow(inbox=inbox, order=order, cycle=cycle)
    process = process_lemon_squeezy_top_up_factory(uow_factory=lambda: uow)

    result = await process(
        inbox_id=INBOX_ID,
        processed_at=END - timedelta(minutes=1),
    )

    assert result.units == 10_000
    assert cycle.top_up_units == 10_000
    assert order.state == "granted"
    assert inbox.processing_status == "processed"
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_payment_immediately_before_cycle_end_grants_to_original_cycle() -> None:
    inbox = _inbox()
    order = _order(checkout_creation_status="ready", provider_checkout_id=str(uuid.uuid4()))
    cycle = _cycle()
    uow = FakeUow(inbox=inbox, order=order, cycle=cycle)
    process = process_lemon_squeezy_top_up_factory(uow_factory=lambda: uow)

    processed_at = END - timedelta(microseconds=1)
    result = await process(inbox_id=INBOX_ID, processed_at=processed_at)

    assert result.units == 10_000
    assert cycle.top_up_units == 10_000
    assert uow.subscription_top_up_grants.grant.expires_at == END
    assert uow.top_up_payments.payment.verified_amount == Decimal(order.settlement_amount)
    assert uow.commit_count == 1


@pytest.mark.asyncio
async def test_payment_at_cycle_end_fails_closed_and_never_moves_to_next_cycle() -> None:
    inbox = _inbox()
    order = _order(checkout_creation_status="ready", provider_checkout_id=str(uuid.uuid4()))
    cycle = _cycle()
    uow = FakeUow(inbox=inbox, order=order, cycle=cycle)
    process = process_lemon_squeezy_top_up_factory(uow_factory=lambda: uow)

    with pytest.raises(LemonSqueezyWebhookError, match="could not be granted safely"):
        await process(inbox_id=INBOX_ID, processed_at=END)

    assert cycle.top_up_units == 0
    assert uow.subscription_top_up_grants.grant is None
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_payment_after_cycle_end_fails_closed_without_retargeting() -> None:
    inbox = _inbox()
    order = _order(checkout_creation_status="ready", provider_checkout_id=str(uuid.uuid4()))
    cycle = _cycle()
    uow = FakeUow(inbox=inbox, order=order, cycle=cycle)
    process = process_lemon_squeezy_top_up_factory(uow_factory=lambda: uow)

    with pytest.raises(LemonSqueezyWebhookError, match="could not be granted safely"):
        await process(inbox_id=INBOX_ID, processed_at=END + timedelta(seconds=1))

    assert cycle.top_up_units == 0
    assert order.quota_cycle_id == CYCLE_ID
    assert uow.subscription_top_up_grants.grant is None
    assert uow.commit_count == 0
