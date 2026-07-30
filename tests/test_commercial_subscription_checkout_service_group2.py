from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from processual_api.billing.commercial_subscription_checkout_service import (
    CommercialActivationDecision,
    CommercialCheckoutChannel,
    CommercialCheckoutConflictError,
    CommercialCheckoutDisabledError,
    CommercialCheckoutEvidenceError,
    CommercialCheckoutOrderState,
    CommercialCheckoutPermissionError,
    CommercialCheckoutPolicy,
    CommercialDecisionOutcome,
    CommercialPaymentEvidence,
    CommercialSubscriptionCheckoutService,
    CreateSubscriptionCheckoutCommand,
    DecideSubscriptionActivationCommand,
    PaymentEvidenceOutcome,
    RecordPaymentEvidenceCommand,
    SubscriptionCheckoutOrder,
    available_checkout_channels,
    build_checkout_view,
    build_commercial_checkout_authority_status,
)

ORDER_ID = UUID("4918da94-7738-47db-b1fa-e3daebf10101")
TENANT_ID = UUID("4918da94-7738-47db-b1fa-e3daebf10102")
SUBSCRIPTION_ID = UUID("4918da94-7738-47db-b1fa-e3daebf10103")
EVIDENCE_ID = UUID("4918da94-7738-47db-b1fa-e3daebf10104")
DECISION_ID = UUID("4918da94-7738-47db-b1fa-e3daebf10105")
JULY = datetime(2026, 7, 1, tzinfo=UTC)
AUGUST = datetime(2026, 8, 1, tzinfo=UTC)
NOW = datetime(2026, 7, 30, 16, 20, tzinfo=UTC)
EXPIRY = datetime(2026, 7, 30, 17, 20, tzinfo=UTC)


class Orders:
    def __init__(self) -> None:
        self.items = {}

    async def get_by_id(self, order_id, *, for_update=False):
        assert isinstance(for_update, bool)
        return self.items.get(order_id)

    async def get_by_idempotency_key(self, key):
        return next(
            (item for item in self.items.values() if item.idempotency_key == key),
            None,
        )

    def add(self, order):
        self.items[order.order_id] = order

    def replace(self, order):
        self.items[order.order_id] = order


class Payments:
    def __init__(self) -> None:
        self.items = []

    async def get_by_provider_reference(self, reference):
        return next(
            (item for item in self.items if item.provider_reference == reference),
            None,
        )

    async def get_latest_for_order(self, order_id):
        return next(
            (item for item in reversed(self.items) if item.order_id == order_id),
            None,
        )

    def add(self, evidence):
        self.items.append(evidence)


class Decisions:
    def __init__(self) -> None:
        self.items = []

    async def get_by_idempotency_key(self, key):
        return next(
            (item for item in self.items if item.idempotency_key == key),
            None,
        )

    async def get_latest_for_order(self, order_id):
        return next(
            (item for item in reversed(self.items) if item.order_id == order_id),
            None,
        )

    def add(self, decision):
        self.items.append(decision)


class Unit:
    def __init__(self) -> None:
        self.orders = Orders()
        self.payments = Payments()
        self.decisions = Decisions()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        del exc
        del traceback
        if exc_type is not None:
            self.rollbacks += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def policy(**overrides):
    values = {
        "enabled": True,
        "writes_enabled": True,
        "activation_enabled": True,
        "grant_bridge_enabled": True,
    }
    values.update(overrides)
    return CommercialCheckoutPolicy(**values)


def order(
    *,
    channel=CommercialCheckoutChannel.LEMON_SQUEEZY,
    country="FR",
    eligible=False,
    settlement_currency="USD",
    settlement_amount=Decimal("29.00"),
    idempotency_key="checkout:academic:1",
):
    return SubscriptionCheckoutOrder(
        order_id=ORDER_ID,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        customer_reference="customer:1",
        plan_code="academic",
        included_units=5_000,
        billing_cycle_reference="2026-07",
        cycle_started_at=JULY,
        cycle_ends_at=AUGUST,
        authoritative_price_usd=Decimal("29.00"),
        selected_channel=channel,
        settlement_currency=settlement_currency,
        settlement_amount=settlement_amount,
        quote_reference="quote:academic:1",
        quote_expires_at=EXPIRY,
        billing_country=country,
        tunisian_address_eligible=eligible,
        customer_choice_preserved=True,
        state=CommercialCheckoutOrderState.DRAFT,
        idempotency_key=idempotency_key,
        created_at=NOW,
    )


def evidence(
    *,
    channel=CommercialCheckoutChannel.LEMON_SQUEEZY,
    outcome=PaymentEvidenceOutcome.VERIFIED,
    amount=Decimal("29.00"),
    currency="USD",
    provider_reference="provider-payment:1",
):
    return CommercialPaymentEvidence(
        evidence_id=EVIDENCE_ID,
        order_id=ORDER_ID,
        provider_reference=provider_reference,
        channel=channel,
        outcome=outcome,
        verified_amount=amount,
        verified_currency=currency,
        immutable_evidence_reference="evidence://payment/1",
        observed_at=NOW,
        idempotency_key="payment-evidence:1",
    )


def decision(
    *,
    authority="platform_admin",
    outcome=CommercialDecisionOutcome.APPROVED,
    key="activation-decision:1",
):
    return CommercialActivationDecision(
        decision_id=DECISION_ID,
        order_id=ORDER_ID,
        outcome=outcome,
        actor_reference="platform-admin:user-1",
        authority_reference=authority,
        approval_reference="billing-cycle-approval:order-1",
        reason="verified payment and approved activation",
        occurred_at=NOW,
        idempotency_key=key,
    )


@pytest.mark.asyncio
async def test_service_is_fail_closed_by_default() -> None:
    service = CommercialSubscriptionCheckoutService(unit_of_work_factory=Unit)

    with pytest.raises(CommercialCheckoutDisabledError):
        await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))


def test_tunisia_channel_is_optional_and_lemon_remains_available() -> None:
    assert available_checkout_channels(
        billing_country="TN",
        tunisian_address_eligible=True,
    ) == (
        CommercialCheckoutChannel.LOCAL_TUNISIA,
        CommercialCheckoutChannel.LEMON_SQUEEZY,
    )

    assert available_checkout_channels(
        billing_country="FR",
        tunisian_address_eligible=False,
    ) == (CommercialCheckoutChannel.LEMON_SQUEEZY,)


def test_local_tunisia_requires_eligible_tn_address() -> None:
    with pytest.raises(ValueError, match="billing country TN"):
        order(
            channel=CommercialCheckoutChannel.LOCAL_TUNISIA,
            country="FR",
            eligible=False,
            settlement_currency="TND",
            settlement_amount=Decimal("91.000"),
        )


def test_local_tunisia_requires_tnd_settlement() -> None:
    with pytest.raises(ValueError, match="must be TND"):
        order(
            channel=CommercialCheckoutChannel.LOCAL_TUNISIA,
            country="TN",
            eligible=True,
        )


@pytest.mark.asyncio
async def test_create_checkout_and_replay_are_idempotent() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    command = CreateSubscriptionCheckoutCommand(order())

    first = await service.create_checkout(command)
    replay = await service.create_checkout(command)

    assert first.committed is True
    assert replay.idempotent_replay is True
    assert unit.commits == 1


@pytest.mark.asyncio
async def test_checkout_idempotency_conflict_is_rejected() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))

    conflicting_order = replace(
        order(),
        quote_reference="quote:academic:conflict",
    )

    with pytest.raises(
        CommercialCheckoutConflictError,
        match="conflicts",
    ):
        await service.create_checkout(CreateSubscriptionCheckoutCommand(conflicting_order))


@pytest.mark.asyncio
async def test_verified_payment_moves_to_activation_review_boundary() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))

    result = await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))

    assert result.order.state is CommercialCheckoutOrderState.PAYMENT_VERIFIED
    assert result.grant_command is None
    assert len(unit.payments.items) == 1


@pytest.mark.asyncio
async def test_webhook_evidence_cannot_directly_grant() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))

    result = await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))

    assert result.grant_command is None
    assert len(unit.decisions.items) == 0


@pytest.mark.asyncio
async def test_payment_currency_mismatch_is_rejected() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))

    with pytest.raises(
        CommercialCheckoutEvidenceError,
        match="currency",
    ):
        await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence(currency="TND")))


@pytest.mark.asyncio
async def test_payment_amount_mismatch_is_rejected() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))

    with pytest.raises(
        CommercialCheckoutEvidenceError,
        match="amount",
    ):
        await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence(amount=Decimal("28.00"))))


@pytest.mark.asyncio
async def test_activation_requires_verified_payment() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))

    with pytest.raises(
        CommercialCheckoutEvidenceError,
        match="verified payment",
    ):
        await service.decide_activation(
            DecideSubscriptionActivationCommand(
                decision=decision(),
                recent_mfa_step_up=True,
            )
        )


@pytest.mark.asyncio
async def test_activation_requires_platform_admin() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))
    await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))

    with pytest.raises(
        CommercialCheckoutPermissionError,
        match="platform_admin",
    ):
        await service.decide_activation(
            DecideSubscriptionActivationCommand(
                decision=decision(authority="platform_supervisor"),
                recent_mfa_step_up=True,
            )
        )


@pytest.mark.asyncio
async def test_activation_requires_recent_mfa_step_up() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))
    await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))

    with pytest.raises(
        CommercialCheckoutPermissionError,
        match="MFA",
    ):
        await service.decide_activation(
            DecideSubscriptionActivationCommand(
                decision=decision(),
                recent_mfa_step_up=False,
            )
        )


@pytest.mark.asyncio
async def test_approved_activation_builds_governed_grant_command() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))
    await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))

    result = await service.decide_activation(
        DecideSubscriptionActivationCommand(
            decision=decision(),
            recent_mfa_step_up=True,
        )
    )

    assert result.order.state is CommercialCheckoutOrderState.ACTIVATION_APPROVED
    assert result.grant_command is not None
    assert result.grant_command.units == 5_000
    assert result.grant_command.invoice_reference.startswith("activation-invoice:")
    assert result.grant_command.authority_reference.startswith("subscription-billing-authority:")
    assert result.grant_command.approval_reference.startswith("billing-cycle-approval:")


@pytest.mark.asyncio
async def test_activation_decision_replay_is_idempotent() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))
    await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))
    command = DecideSubscriptionActivationCommand(
        decision=decision(),
        recent_mfa_step_up=True,
    )

    first = await service.decide_activation(command)
    replay = await service.decide_activation(command)

    assert first.committed is True
    assert replay.idempotent_replay is True
    assert replay.grant_command is not None
    assert len(unit.decisions.items) == 1


@pytest.mark.asyncio
async def test_denied_activation_does_not_build_grant() -> None:
    unit = Unit()
    service = CommercialSubscriptionCheckoutService(
        unit_of_work_factory=lambda: unit,
        policy=policy(),
    )
    await service.create_checkout(CreateSubscriptionCheckoutCommand(order()))
    await service.record_payment_evidence(RecordPaymentEvidenceCommand(evidence()))

    result = await service.decide_activation(
        DecideSubscriptionActivationCommand(
            decision=decision(outcome=CommercialDecisionOutcome.DENIED),
            recent_mfa_step_up=True,
        )
    )

    assert result.order.state is CommercialCheckoutOrderState.ACTIVATION_REJECTED
    assert result.grant_command is None


def test_checkout_view_exposes_clear_states_and_channel_choice() -> None:
    view = build_checkout_view(
        order=order(
            channel=CommercialCheckoutChannel.LOCAL_TUNISIA,
            country="TN",
            eligible=True,
            settlement_currency="TND",
            settlement_amount=Decimal("91.000"),
        ),
        policy=policy(),
    )

    assert view.customer_choice_preserved is True
    assert view.available_channels == (
        "local_tunisia",
        "lemon_squeezy",
    )
    assert view.authoritative_price_usd == "29.00"
    assert view.settlement_currency == "TND"
    assert view.messages


def test_default_view_and_status_remain_disabled() -> None:
    view = build_checkout_view(order=None)
    status = build_commercial_checkout_authority_status()

    assert view.state.value == "disabled"
    assert status["enabled"] is False
    assert status["writes_enabled"] is False
    assert status["provider_runtime_enabled"] is False
    assert status["webhook_runtime_enabled"] is False
    assert status["activation_enabled"] is False
    assert status["grant_bridge_enabled"] is False
    assert status["webhook_direct_grant_prohibited"] is True
