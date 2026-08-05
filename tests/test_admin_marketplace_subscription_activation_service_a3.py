from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.errors import (
    SubscriptionActivationNotReadyError,
)
from processual_api.admin_marketplace.subscription_activation_service import (
    SubscriptionActivationOrchestrator,
)

NOW = datetime(2026, 8, 5, 16, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
OFFER_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
PLAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
SUBSCRIPTION_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")
ACTIVATION_ID = uuid.UUID("50000000-0000-0000-0000-000000000001")
EVENT_ID = uuid.UUID("60000000-0000-0000-0000-000000000001")


class SingleRepository:
    def __init__(self, item=None) -> None:
        self.item = item
        self.items = []

    async def get_by_id(self, item_id, *, for_update=False):
        if self.item is not None and self.item.id == item_id:
            return self.item
        return next((item for item in self.items if item.id == item_id), None)

    def add(self, item):
        self.items.append(item)


class Orders(SingleRepository):
    async def get_by_ref(self, order_ref, *, for_update=False):
        return self.item if self.item.order_ref == order_ref else None


class Contracts(SingleRepository):
    async def get_by_order_id(self, order_id, *, for_update=False):
        return self.item if self.item.order_id == order_id else None


class Verifications(Contracts):
    pass


class Eligibility(SingleRepository):
    async def get_by_customer_ref(self, customer_ref, *, for_update=False):
        return self.item if self.item.customer_ref == customer_ref else None


class Subscriptions(SingleRepository):
    def __init__(self, active=None) -> None:
        super().__init__()
        self.active = active

    async def get_active_by_customer_ref(self, customer_ref, *, for_update=False):
        if self.active is not None and self.active.customer_ref == customer_ref:
            return self.active
        return None


class Activations(SingleRepository):
    async def get_by_order_id(self, order_id, *, for_update=False):
        return next((item for item in self.items if item.order_id == order_id), None)

    async def get_by_idempotency_key_hash(self, key_hash):
        return next(
            (item for item in self.items if item.activation_idempotency_key_hash == key_hash),
            None,
        )


class Audit:
    def __init__(self) -> None:
        self.items = []

    def append(self, item):
        self.items.append(item)


class Unit:
    def __init__(self, *, active_subscription=None) -> None:
        self.orders = Orders(order())
        self.contracts = Contracts(SimpleNamespace(order_id=ORDER_ID, status="completed"))
        self.payment_verifications = Verifications(SimpleNamespace(order_id=ORDER_ID, status="verified"))
        self.channel_eligibilities = Eligibility(eligibility())
        self.subscriptions = Subscriptions(active_subscription)
        self.entitlement_activations = Activations()
        self.offers = SingleRepository(offer())
        self.plans = SingleRepository(plan())
        self.commercial_audit = Audit()
        self.commit_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commit_calls += 1


def order():
    return SimpleNamespace(
        id=ORDER_ID,
        order_ref="ord_001",
        customer_ref="customer_001",
        offer_id=OFFER_ID,
        plan_id=PLAN_ID,
        billing_period="monthly",
        selected_channel="maestro_direct",
        country_code="TN",
        currency="TND",
        subtotal_amount=Decimal("49.900"),
        status="ready_for_activation",
        contract_status="completed",
        payment_requirement="required",
        payment_status="verified",
        completed_at=None,
        updated_at=NOW,
    )


def eligibility(**changes):
    values = {
        "id": uuid.uuid4(),
        "customer_ref": "customer_001",
        "address_status": "confirmed",
        "country_code": "TN",
        "maestro_direct_status": "eligible",
        "admin_review_required": False,
        "automatic_activation_allowed": True,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def offer(**changes):
    values = {
        "id": OFFER_ID,
        "plan_id": PLAN_ID,
        "status": "published",
        "sales_channel": "maestro_direct",
        "currency": "TND",
        "billing_period": "monthly",
        "amount": Decimal("49.900"),
        "effective_at": None,
        "expires_at": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def plan():
    return SimpleNamespace(
        id=PLAN_ID,
        entitlement_profile_ref="starter_entitlements_v1",
    )


def active_subscription():
    return SimpleNamespace(
        id=uuid.uuid4(),
        customer_ref="customer_001",
        status="active",
    )


def service(unit):
    ids = iter((SUBSCRIPTION_ID, ACTIVATION_ID))
    refs = iter(
        (
            uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
            uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"),
        )
    )
    return SubscriptionActivationOrchestrator(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: next(ids),
        reference_factory=lambda: next(refs),
        event_id_factory=lambda: EVENT_ID,
    )


def kwargs():
    return {
        "order_ref": "ord_001",
        "correlation_id": "corr_activation_001",
        "idempotency_key": "subscription-activation-idempotency-0001",
    }


@pytest.mark.asyncio
async def test_activation_creates_subscription_entitlement_and_audit_atomically() -> None:
    unit = Unit()

    result = await service(unit).activate_ready_order(**kwargs())

    assert result.status == "activated"
    assert result.subscription_status == "active"
    assert result.order_status == "activated"
    assert result.entitlement_profile_ref == "starter_entitlements_v1"
    assert unit.commit_calls == 1
    assert len(unit.subscriptions.items) == 1
    assert len(unit.entitlement_activations.items) == 1
    activation = unit.entitlement_activations.items[0]
    assert activation.automatic_activation_allowed is True
    assert activation.order_id == ORDER_ID
    audit = unit.commercial_audit.items[0]
    assert audit.action == "subscription_activation_decided"
    assert audit.platform_authority == "system"


@pytest.mark.asyncio
async def test_activation_replay_does_not_duplicate_or_commit() -> None:
    unit = Unit()
    orchestrator = service(unit)
    first = await orchestrator.activate_ready_order(**kwargs())
    replay = await orchestrator.activate_ready_order(**kwargs())

    assert replay.subscription_ref == first.subscription_ref
    assert replay.reason_code == "subscription_already_activated"
    assert unit.commit_calls == 1
    assert len(unit.subscriptions.items) == 1
    assert len(unit.commercial_audit.items) == 1


@pytest.mark.asyncio
async def test_activation_fails_closed_when_automatic_gate_is_disabled() -> None:
    unit = Unit()
    unit.channel_eligibilities.item = eligibility(automatic_activation_allowed=False)

    with pytest.raises(SubscriptionActivationNotReadyError) as captured:
        await service(unit).activate_ready_order(**kwargs())

    assert captured.value.reason_code == "automatic_activation_not_allowed"
    assert unit.commit_calls == 0
    assert unit.subscriptions.items == []


@pytest.mark.asyncio
async def test_activation_blocks_a_second_active_customer_subscription() -> None:
    unit = Unit(active_subscription=active_subscription())

    with pytest.raises(SubscriptionActivationNotReadyError) as captured:
        await service(unit).activate_ready_order(**kwargs())

    assert captured.value.reason_code == "active_subscription_conflict"
    assert unit.commit_calls == 0


@pytest.mark.asyncio
async def test_activation_rechecks_offer_at_execution_time() -> None:
    unit = Unit()
    unit.offers.item = offer(status="retired")

    with pytest.raises(SubscriptionActivationNotReadyError) as captured:
        await service(unit).activate_ready_order(**kwargs())

    assert captured.value.reason_code == "offer_no_longer_valid"
    assert unit.commit_calls == 0
