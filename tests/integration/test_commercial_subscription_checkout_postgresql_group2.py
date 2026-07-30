from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_subscription_checkout_service import (
    CommercialActivationDecision,
    CommercialCheckoutChannel,
    CommercialCheckoutOrderState,
    CommercialCheckoutPolicy,
    CommercialDecisionOutcome,
    CommercialPaymentEvidence,
    CommercialSubscriptionCheckoutService,
    CreateSubscriptionCheckoutCommand,
    DecideSubscriptionActivationCommand,
    PaymentEvidenceOutcome,
    RecordPaymentEvidenceCommand,
    SubscriptionCheckoutOrder,
)
from processual_api.billing.commercial_subscription_checkout_unit_of_work import (
    SqlAlchemyCommercialSubscriptionCheckoutUnitOfWork,
)

DATABASE_URL = os.environ.get(
    "PMK_COMMERCIAL_CHECKOUT_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=("Set PMK_COMMERCIAL_CHECKOUT_INTEGRATION_DATABASE_URL to run the PostgreSQL checkout persistence gate."),
)

ORDER_ID = UUID("41c806f3-6fc2-439e-8bd3-873206196101")
TENANT_ID = UUID("41c806f3-6fc2-439e-8bd3-873206196102")
SUBSCRIPTION_ID = UUID("41c806f3-6fc2-439e-8bd3-873206196103")
EVIDENCE_ID = UUID("41c806f3-6fc2-439e-8bd3-873206196104")
DECISION_ID = UUID("41c806f3-6fc2-439e-8bd3-873206196105")
NOW = datetime(2026, 7, 30, 16, 45, tzinfo=UTC)
START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 8, 1, tzinfo=UTC)
QUOTE_EXPIRY = datetime(2026, 7, 30, 17, 45, tzinfo=UTC)


@pytest_asyncio.fixture
async def postgresql_checkout_gate():
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def clear_rows() -> None:
        async with session_factory() as session:
            await session.execute(text("DELETE FROM commercial_subscription_activation_decisions"))
            await session.execute(text("DELETE FROM commercial_subscription_payment_evidence"))
            await session.execute(text("DELETE FROM commercial_subscription_checkout_orders"))
            await session.commit()

    await clear_rows()
    try:
        yield engine, session_factory
    finally:
        await clear_rows()
        await engine.dispose()


def _policy() -> CommercialCheckoutPolicy:
    return CommercialCheckoutPolicy(
        enabled=True,
        writes_enabled=True,
        provider_runtime_enabled=False,
        webhook_runtime_enabled=False,
        activation_enabled=True,
        grant_bridge_enabled=True,
    )


def _service(session_factory):
    return CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: SqlAlchemyCommercialSubscriptionCheckoutUnitOfWork(session_factory),
        policy=_policy(),
    )


def _order() -> SubscriptionCheckoutOrder:
    return SubscriptionCheckoutOrder(
        order_id=ORDER_ID,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        customer_reference="customer:postgresql-gate",
        plan_code="academic",
        included_units=5_000,
        billing_cycle_reference="2026-07",
        cycle_started_at=START,
        cycle_ends_at=END,
        authoritative_price_usd=Decimal("29.00"),
        selected_channel=CommercialCheckoutChannel.LEMON_SQUEEZY,
        settlement_currency="USD",
        settlement_amount=Decimal("29.00"),
        quote_reference="quote:postgresql-gate",
        quote_expires_at=QUOTE_EXPIRY,
        billing_country="FR",
        tunisian_address_eligible=False,
        customer_choice_preserved=True,
        state=CommercialCheckoutOrderState.DRAFT,
        idempotency_key="checkout:postgresql-gate",
        created_at=NOW,
    )


def _evidence() -> CommercialPaymentEvidence:
    return CommercialPaymentEvidence(
        evidence_id=EVIDENCE_ID,
        order_id=ORDER_ID,
        provider_reference="provider:postgresql-gate",
        channel=CommercialCheckoutChannel.LEMON_SQUEEZY,
        outcome=PaymentEvidenceOutcome.VERIFIED,
        verified_amount=Decimal("29.00"),
        verified_currency="USD",
        immutable_evidence_reference=("evidence://postgresql/checkout-payment"),
        observed_at=NOW,
        idempotency_key="evidence:postgresql-gate",
    )


def _decision() -> CommercialActivationDecision:
    return CommercialActivationDecision(
        decision_id=DECISION_ID,
        order_id=ORDER_ID,
        outcome=CommercialDecisionOutcome.APPROVED,
        actor_reference="platform-admin:postgresql-gate",
        authority_reference="platform_admin",
        approval_reference=("billing-cycle-approval:postgresql-gate"),
        reason="PostgreSQL qualification approval",
        occurred_at=NOW,
        idempotency_key="decision:postgresql-gate",
    )


@pytest.mark.asyncio
async def test_real_postgresql_checkout_payment_activation_is_atomic(
    postgresql_checkout_gate,
) -> None:
    _, session_factory = postgresql_checkout_gate
    service = _service(session_factory)

    created = await service.create_checkout(CreateSubscriptionCheckoutCommand(_order()))
    replay = await service.create_checkout(CreateSubscriptionCheckoutCommand(_order()))

    assert created.committed is True
    assert replay.idempotent_replay is True

    paid = await service.record_payment_evidence(RecordPaymentEvidenceCommand(_evidence()))
    assert paid.order.state is CommercialCheckoutOrderState.PAYMENT_VERIFIED
    assert paid.grant_command is None

    activated = await service.decide_activation(
        DecideSubscriptionActivationCommand(
            decision=_decision(),
            recent_mfa_step_up=True,
        )
    )
    assert activated.order.state is CommercialCheckoutOrderState.ACTIVATION_APPROVED
    assert activated.grant_command is not None
    assert activated.grant_command.units == 5_000

    decision_replay = await service.decide_activation(
        DecideSubscriptionActivationCommand(
            decision=_decision(),
            recent_mfa_step_up=True,
        )
    )
    assert decision_replay.idempotent_replay is True
    assert decision_replay.grant_command is not None

    async with session_factory() as session:
        order_row = (
            await session.execute(
                text(
                    "SELECT state, version, selected_channel, "
                    "settlement_currency, settlement_amount "
                    "FROM commercial_subscription_checkout_orders "
                    "WHERE order_id = :order_id"
                ),
                {"order_id": ORDER_ID},
            )
        ).one()

        payment_count = (
            await session.execute(
                text("SELECT count(*) FROM commercial_subscription_payment_evidence WHERE order_id = :order_id"),
                {"order_id": ORDER_ID},
            )
        ).scalar_one()

        decision_count = (
            await session.execute(
                text("SELECT count(*) FROM commercial_subscription_activation_decisions WHERE order_id = :order_id"),
                {"order_id": ORDER_ID},
            )
        ).scalar_one()

    assert order_row.state == "activation_approved"
    assert order_row.version == 2
    assert order_row.selected_channel == "lemon_squeezy"
    assert order_row.settlement_currency == "USD"
    assert order_row.settlement_amount == Decimal("29.000")
    assert payment_count == 1
    assert decision_count == 1
