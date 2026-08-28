from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.local_tunisia_top_up_payment import (
    LocalTunisiaTopUpPaymentError,
    VerifyLocalTunisiaTopUpPaymentCommand,
    verify_local_tunisia_top_up_payment_factory,
)
from processual_api.admin_marketplace.subscription_top_up_order import (
    CreateSubscriptionTopUpOrderCommand,
    create_subscription_top_up_order_factory,
)
from processual_api.admin_marketplace.subscription_top_up_reversal import (
    ReverseSubscriptionTopUpCommand,
    SubscriptionTopUpReversalError,
    reverse_subscription_top_up_factory,
)
from processual_api.billing.commercial_currency_settlement_contracts import ExchangeRateQuote
from processual_api.billing.commercial_settings_top_up_checkout_contracts import TopUpCheckoutChannel
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_CATALOG_VERSION

NOW = datetime(2026, 8, 28, 9, 0, tzinfo=UTC)
START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 9, 1, tzinfo=UTC)
ORDER_ID = uuid.uuid4()
SUBSCRIPTION_ID = uuid.uuid4()
PLAN_ID = uuid.uuid4()
CYCLE_ID = uuid.uuid4()
CUSTOMER = "customer_001"
PROVIDER_REFERENCE = "tn-bank:receipt:20260828-001"
EVIDENCE_REFERENCE = "evidence:immutable:20260828-001"


class ByIdRepo:
    def __init__(self, value: object | None) -> None:
        self.value = value

    async def get_by_id(self, value_id, *, for_update: bool = False):
        del for_update
        if self.value is None or self.value.id != value_id:
            return None
        return self.value


class OrderRepo:
    def __init__(self) -> None:
        self.order = None

    async def get_by_id(self, value_id, *, for_update: bool = False):
        del for_update
        if self.order is None or self.order.id != value_id:
            return None
        return self.order

    async def get_by_idempotency_key(self, key: str):
        if self.order is None or self.order.idempotency_key != key:
            return None
        return self.order

    def add(self, order: object) -> None:
        self.order = order


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
        del for_update
        if self.grant is None or self.grant.order_id != order_id:
            return None
        return self.grant

    async def get_by_idempotency_key(self, key: str, *, for_update: bool = False):
        del for_update
        if self.grant is None or self.grant.grant_idempotency_key != key:
            return None
        return self.grant

    def add(self, grant: object) -> None:
        self.grant = grant


class ReversalRepo:
    def __init__(self) -> None:
        self.reversal = None

    async def get_by_provider_event_ref(self, provider_event_ref: str, *, for_update: bool = False):
        del for_update
        if self.reversal is None or self.reversal.provider_event_ref != provider_event_ref:
            return None
        return self.reversal

    async def get_by_grant_id(self, grant_id, *, for_update: bool = False):
        del for_update
        if self.reversal is None or self.reversal.grant_id != grant_id:
            return None
        return self.reversal

    def add(self, reversal: object) -> None:
        self.reversal = reversal


class SharedUow:
    def __init__(self) -> None:
        self.subscription = SimpleNamespace(
            id=SUBSCRIPTION_ID,
            customer_ref=CUSTOMER,
            plan_id=PLAN_ID,
            status="active",
        )
        self.plan = SimpleNamespace(id=PLAN_ID, plan_code="starter")
        self.cycle = SimpleNamespace(
            id=CYCLE_ID,
            subscription_id=SUBSCRIPTION_ID,
            customer_ref=CUSTOMER,
            metric_code="credits",
            period_start=START,
            period_end=END,
            plan_code="starter",
            plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
            base_limit_units=10_000,
            spendable_rollover_units=0,
            used_units=8_000,
            top_up_units=0,
            version=1,
        )
        self.subscriptions = ByIdRepo(self.subscription)
        self.plans = ByIdRepo(self.plan)
        self.subscription_quota_cycles = ByIdRepo(self.cycle)
        self.top_up_orders = OrderRepo()
        self.top_up_payments = PaymentRepo()
        self.subscription_top_up_grants = GrantRepo()
        self.subscription_top_up_reversals = ReversalRepo()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.commit_count += 1


class FixedFxProvider:
    async def quote_usd_to_tnd(self, *, requested_at: datetime) -> ExchangeRateQuote:
        return ExchangeRateQuote(
            base_currency="USD",
            settlement_currency="TND",
            rate=Decimal("3.100000"),
            source="authoritative-treasury-process",
            reference="fx-20260828-001",
            observed_at=requested_at - timedelta(minutes=5),
            expires_at=requested_at + timedelta(minutes=55),
        )


async def _eligible(customer_ref: str, subscription_id: uuid.UUID, requested_at: datetime) -> bool:
    return customer_ref == CUSTOMER and subscription_id == SUBSCRIPTION_ID and requested_at == NOW


def _create_service(uow: SharedUow):
    return create_subscription_top_up_order_factory(
        unit_of_work_factory=lambda: uow,
        local_tunisia_eligibility_resolver=_eligible,
        exchange_rate_provider=FixedFxProvider(),
    )


def _verify_service(uow: SharedUow):
    return verify_local_tunisia_top_up_payment_factory(unit_of_work_factory=lambda: uow)


def _reverse_service(uow: SharedUow):
    return reverse_subscription_top_up_factory(unit_of_work_factory=lambda: uow)


@pytest.mark.asyncio
async def test_local_tunisia_order_verify_grant_replay_and_reversal_are_one_coherent_flow() -> None:
    uow = SharedUow()
    create = _create_service(uow)
    verify = _verify_service(uow)
    reverse = _reverse_service(uow)

    created = await create(
        CreateSubscriptionTopUpOrderCommand(
            order_id=ORDER_ID,
            customer_ref=CUSTOMER,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            requested_units=10_000,
            channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
            idempotency_key="local-e2e-001",
            created_at=NOW,
        )
    )
    assert created.settlement_currency == "TND"
    assert uow.top_up_orders.order.exchange_rate_reference == "fx-20260828-001"

    amount_tnd = Decimal(created.settlement_amount)
    first = await verify(
        VerifyLocalTunisiaTopUpPaymentCommand(
            order_id=ORDER_ID,
            customer_ref=CUSTOMER,
            provider_reference=PROVIDER_REFERENCE,
            amount_tnd=amount_tnd,
            evidence_reference=EVIDENCE_REFERENCE,
            verified_at=NOW,
        )
    )
    replay = await verify(
        VerifyLocalTunisiaTopUpPaymentCommand(
            order_id=ORDER_ID,
            customer_ref=CUSTOMER,
            provider_reference=PROVIDER_REFERENCE,
            amount_tnd=amount_tnd,
            evidence_reference=EVIDENCE_REFERENCE,
            verified_at=NOW,
        )
    )
    assert first.replayed_grant is False
    assert replay.replayed_grant is True
    assert uow.cycle.top_up_units == 10_000
    assert uow.cycle.version == 2

    reversed_result = await reverse(
        ReverseSubscriptionTopUpCommand(
            order_id=ORDER_ID,
            provider_event_ref="tn-bank:refund:20260828-001",
            reason_code="provider_refund",
            reversed_at=NOW,
        )
    )
    replayed_reversal = await reverse(
        ReverseSubscriptionTopUpCommand(
            order_id=ORDER_ID,
            provider_event_ref="tn-bank:refund:20260828-001",
            reason_code="provider_refund",
            reversed_at=NOW,
        )
    )
    assert reversed_result.outcome == "reversed"
    assert replayed_reversal.idempotent_replay is True
    assert uow.cycle.top_up_units == 0
    assert uow.cycle.version == 3
    assert uow.commit_count == 3


@pytest.mark.asyncio
async def test_local_tunisia_e2e_rejects_amount_mismatch_before_grant() -> None:
    uow = SharedUow()
    created = await _create_service(uow)(
        CreateSubscriptionTopUpOrderCommand(
            order_id=ORDER_ID,
            customer_ref=CUSTOMER,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            requested_units=10_000,
            channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
            idempotency_key="local-e2e-mismatch",
            created_at=NOW,
        )
    )

    with pytest.raises(LocalTunisiaTopUpPaymentError, match="amount conflicts"):
        await _verify_service(uow)(
            VerifyLocalTunisiaTopUpPaymentCommand(
                order_id=ORDER_ID,
                customer_ref=CUSTOMER,
                provider_reference="tn-bank:receipt:mismatch",
                amount_tnd=Decimal(created.settlement_amount) - Decimal("0.001"),
                evidence_reference="evidence:mismatch",
                verified_at=NOW,
            )
        )

    assert uow.cycle.top_up_units == 0
    assert uow.subscription_top_up_grants.grant is None


@pytest.mark.asyncio
async def test_second_distinct_reversal_is_rejected_after_successful_e2e_reversal() -> None:
    uow = SharedUow()
    created = await _create_service(uow)(
        CreateSubscriptionTopUpOrderCommand(
            order_id=ORDER_ID,
            customer_ref=CUSTOMER,
            subscription_id=SUBSCRIPTION_ID,
            quota_cycle_id=CYCLE_ID,
            requested_units=10_000,
            channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
            idempotency_key="local-e2e-reversal",
            created_at=NOW,
        )
    )
    await _verify_service(uow)(
        VerifyLocalTunisiaTopUpPaymentCommand(
            order_id=ORDER_ID,
            customer_ref=CUSTOMER,
            provider_reference=PROVIDER_REFERENCE,
            amount_tnd=Decimal(created.settlement_amount),
            evidence_reference=EVIDENCE_REFERENCE,
            verified_at=NOW,
        )
    )
    reverse = _reverse_service(uow)
    await reverse(
        ReverseSubscriptionTopUpCommand(
            order_id=ORDER_ID,
            provider_event_ref="tn-bank:refund:first",
            reason_code="provider_refund",
            reversed_at=NOW,
        )
    )

    with pytest.raises(SubscriptionTopUpReversalError, match="already has a reversal decision"):
        await reverse(
            ReverseSubscriptionTopUpCommand(
                order_id=ORDER_ID,
                provider_event_ref="tn-bank:refund:second",
                reason_code="provider_refund",
                reversed_at=NOW,
            )
        )
