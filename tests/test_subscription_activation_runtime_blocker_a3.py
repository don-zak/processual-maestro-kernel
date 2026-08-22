from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
    build_subscription_quota_profiles,
)
from processual_api.admin_marketplace.subscription_activation_service import (
    SubscriptionActivationOrchestrator,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
)

NOW = datetime(2026, 8, 17, 20, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
PLAN_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
OFFER_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")


class _OrderRepository:
    def __init__(self, order) -> None:
        self.order = order

    async def get_by_ref(self, order_ref, *, for_update=False):
        if self.order.order_ref == order_ref:
            return self.order
        return None


class _ActivationRepository:
    def __init__(self) -> None:
        self.by_order = {}
        self.by_hash = {}

    async def get_by_order_id(self, order_id, *, for_update=False):
        return self.by_order.get(order_id)

    async def get_by_idempotency_key_hash(self, key_hash):
        return self.by_hash.get(key_hash)

    def add(self, activation) -> None:
        self.by_order[activation.order_id] = activation
        self.by_hash[activation.activation_idempotency_key_hash] = activation


class _SubscriptionRepository:
    def __init__(self) -> None:
        self.by_id = {}

    async def get_by_id(self, subscription_id, *, for_update=False):
        return self.by_id.get(subscription_id)

    async def get_active_by_customer_ref(self, customer_ref, *, for_update=False):
        return next(
            (
                item
                for item in self.by_id.values()
                if item.customer_ref == customer_ref and item.status == "active"
            ),
            None,
        )

    def add(self, subscription) -> None:
        self.by_id[subscription.id] = subscription


class _SingleRecordRepository:
    def __init__(self, record, *, key_name: str) -> None:
        self.record = record
        self.key_name = key_name

    async def get_by_order_id(self, order_id, *, for_update=False):
        if self.key_name != "order_id":
            raise AssertionError("repository does not support order lookup")
        if getattr(self.record, self.key_name) == order_id:
            return self.record
        return None

    async def get_by_customer_ref(self, customer_ref, *, for_update=False):
        if self.key_name != "customer_ref":
            raise AssertionError("repository does not support customer lookup")
        if getattr(self.record, self.key_name) == customer_ref:
            return self.record
        return None

    async def get_by_id(self, record_id, *, for_update=False):
        if self.key_name != "id":
            raise AssertionError("repository does not support id lookup")
        if getattr(self.record, self.key_name) == record_id:
            return self.record
        return None


class _RuntimeRepository:
    def __init__(self) -> None:
        self.by_subscription = {}

    async def get_by_subscription_id(self, subscription_id, *, for_update=False):
        return self.by_subscription.get(subscription_id)

    def add(self, runtime) -> None:
        self.by_subscription[runtime.subscription_id] = runtime


class _QuotaCycleRepository:
    def __init__(self) -> None:
        self.added = []
        self.fail_on_add = False

    async def get_current(
        self,
        *,
        subscription_id,
        metric_code,
        occurred_at,
        for_update=False,
    ):
        return next(
            (
                item
                for item in self.added
                if item.subscription_id == subscription_id
                and item.metric_code == metric_code
                and item.period_start <= occurred_at < item.period_end
            ),
            None,
        )

    def add(self, cycle) -> None:
        if self.fail_on_add:
            raise RuntimeError("forced quota persistence failure")
        self.added.append(cycle)


class _AuditRepository:
    def __init__(self) -> None:
        self.added = []

    def append(self, record) -> None:
        self.added.append(record)


class _UnitOfWork:
    def __init__(self, *, order, contract, eligibility, offer, plan) -> None:
        self.orders = _OrderRepository(order)
        self.entitlement_activations = _ActivationRepository()
        self.subscriptions = _SubscriptionRepository()
        self.contracts = _SingleRecordRepository(contract, key_name="order_id")
        self.payment_verifications = _SingleRecordRepository(None, key_name="order_id")
        self.channel_eligibilities = _SingleRecordRepository(
            eligibility,
            key_name="customer_ref",
        )
        self.offers = _SingleRecordRepository(offer, key_name="id")
        self.plans = _SingleRecordRepository(plan, key_name="id")
        self.subscription_runtime = _RuntimeRepository()
        self.subscription_quota_cycles = _QuotaCycleRepository()
        self.commercial_audit = _AuditRepository()
        self.commit_count = 0
        self._snapshot = None
        self._commits_before_enter = 0

    async def __aenter__(self):
        order = self.orders.order
        self._commits_before_enter = self.commit_count
        self._snapshot = {
            "order_status": order.status,
            "order_completed_at": order.completed_at,
            "order_updated_at": order.updated_at,
            "subscriptions": dict(self.subscriptions.by_id),
            "activations_by_order": dict(self.entitlement_activations.by_order),
            "activations_by_hash": dict(self.entitlement_activations.by_hash),
            "runtime": dict(self.subscription_runtime.by_subscription),
            "quota_cycles": list(self.subscription_quota_cycles.added),
            "audit": list(self.commercial_audit.added),
        }
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if exc is not None or self.commit_count == self._commits_before_enter:
            self._restore_snapshot()

    async def commit(self) -> None:
        self.commit_count += 1

    def _restore_snapshot(self) -> None:
        if self._snapshot is None:
            return
        order = self.orders.order
        order.status = self._snapshot["order_status"]
        order.completed_at = self._snapshot["order_completed_at"]
        order.updated_at = self._snapshot["order_updated_at"]
        self.subscriptions.by_id = dict(self._snapshot["subscriptions"])
        self.entitlement_activations.by_order = dict(
            self._snapshot["activations_by_order"]
        )
        self.entitlement_activations.by_hash = dict(
            self._snapshot["activations_by_hash"]
        )
        self.subscription_runtime.by_subscription = dict(self._snapshot["runtime"])
        self.subscription_quota_cycles.added = list(self._snapshot["quota_cycles"])
        self.commercial_audit.added = list(self._snapshot["audit"])


def _fixture() -> tuple[_UnitOfWork, object]:
    projection = build_commercial_plan_projections()[0]
    quota_profile = next(
        profile
        for profile in build_subscription_quota_profiles()
        if profile.profile_ref == projection.quota_profile_ref
    )
    customer_ref = "customer-blocker-1"
    order_ref = "ord_blocker_1"
    offer_ref = "offer_blocker_1"
    order = SimpleNamespace(
        id=ORDER_ID,
        order_ref=order_ref,
        customer_ref=customer_ref,
        offer_id=OFFER_ID,
        plan_id=PLAN_ID,
        status="ready_for_activation",
        contract_status="completed",
        payment_requirement="not_required",
        payment_status="not_required",
        selected_channel="maestro_direct",
        country_code="TN",
        currency="TND",
        total_amount=Decimal("0"),
        subtotal_amount=Decimal("0"),
        billing_period="monthly",
        offer_snapshot={
            "offer_ref": offer_ref,
            "plan_ref": projection.plan_code,
            "currency": "TND",
            "sales_channel": "maestro_direct",
            "snapshot_at": NOW.isoformat(),
        },
        completed_at=None,
        updated_at=NOW,
    )
    contract = SimpleNamespace(
        order_id=ORDER_ID,
        customer_ref=customer_ref,
        status="completed",
    )
    eligibility = SimpleNamespace(
        customer_ref=customer_ref,
        address_status="confirmed",
        country_code="TN",
        maestro_direct_status="eligible",
        admin_review_required=False,
        automatic_activation_allowed=True,
    )
    offer = SimpleNamespace(
        id=OFFER_ID,
        plan_id=PLAN_ID,
        offer_code=offer_ref,
        status="published",
        sales_channel="maestro_direct",
        currency="TND",
        billing_period="monthly",
        amount=Decimal("0"),
        effective_at=NOW,
        expires_at=None,
    )
    plan = SimpleNamespace(
        id=PLAN_ID,
        plan_code=projection.plan_code,
        entitlement_profile_ref=projection.entitlement_profile_ref,
        quota_profile_ref=projection.quota_profile_ref,
    )
    return (
        _UnitOfWork(
            order=order,
            contract=contract,
            eligibility=eligibility,
            offer=offer,
            plan=plan,
        ),
        quota_profile,
    )


def _orchestrator(unit: _UnitOfWork) -> SubscriptionActivationOrchestrator:
    ids = iter(
        (
            uuid.UUID("20000000-0000-0000-0000-000000000001"),
            uuid.UUID("20000000-0000-0000-0000-000000000002"),
        )
    )
    refs = iter(
        (
            uuid.UUID("30000000-0000-0000-0000-000000000001"),
            uuid.UUID("30000000-0000-0000-0000-000000000002"),
        )
    )
    return SubscriptionActivationOrchestrator(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: next(ids),
        reference_factory=lambda: next(refs),
        event_id_factory=lambda: uuid.UUID(
            "40000000-0000-0000-0000-000000000001"
        ),
    )


def _assert_cycle_matches_profile(unit: _UnitOfWork, quota_profile: object) -> None:
    assert len(unit.subscription_quota_cycles.added) == 1
    cycle = unit.subscription_quota_cycles.added[0]
    metric = quota_profile.metrics[0]
    projection = build_commercial_plan_projections()[0]
    assert cycle.metric_code == metric.metric_code
    assert cycle.base_limit_units == metric.limit_units
    assert cycle.plan_code == projection.plan_code
    assert cycle.plan_catalog_version == PLAN_FULFILLMENT_CATALOG_VERSION
    assert tuple(cycle.entitlement_codes) == projection.entitlement_codes


@pytest.mark.asyncio
async def test_direct_activation_bootstraps_runtime_and_quota_in_same_commit() -> None:
    unit, quota_profile = _fixture()
    service = _orchestrator(unit)

    result = await service.activate_ready_order(
        order_ref="ord_blocker_1",
        correlation_id="corr-blocker-1-success",
        idempotency_key="idem-blocker-1",
    )

    assert result.reason_code == "subscription_activated"
    assert result.subscription_status == "active"
    assert result.order_status == "activated"
    assert unit.commit_count == 1
    assert len(unit.subscriptions.by_id) == 1
    assert len(unit.entitlement_activations.by_order) == 1
    assert len(unit.subscription_runtime.by_subscription) == 1
    runtime = unit.subscription_runtime.by_subscription[result.subscription_id]
    assert runtime.customer_ref == result.customer_ref
    assert runtime.entitlement_profile_ref == result.entitlement_profile_ref
    assert runtime.quota_profile_ref == quota_profile.profile_ref
    assert runtime.access_stage == "active"
    _assert_cycle_matches_profile(unit, quota_profile)
    assert len(unit.commercial_audit.added) == 1


@pytest.mark.asyncio
async def test_runtime_quota_failure_rolls_back_entire_activation_unit() -> None:
    unit, _ = _fixture()
    unit.subscription_quota_cycles.fail_on_add = True
    service = _orchestrator(unit)

    with pytest.raises(RuntimeError, match="forced quota persistence failure"):
        await service.activate_ready_order(
            order_ref="ord_blocker_1",
            correlation_id="corr-blocker-1-rollback",
            idempotency_key="idem-blocker-1",
        )

    assert unit.commit_count == 0
    assert unit.orders.order.status == "ready_for_activation"
    assert unit.orders.order.completed_at is None
    assert unit.subscriptions.by_id == {}
    assert unit.entitlement_activations.by_order == {}
    assert unit.entitlement_activations.by_hash == {}
    assert unit.subscription_runtime.by_subscription == {}
    assert unit.subscription_quota_cycles.added == []
    assert unit.commercial_audit.added == []


@pytest.mark.asyncio
async def test_activation_replay_does_not_duplicate_runtime_or_quota() -> None:
    unit, quota_profile = _fixture()
    service = _orchestrator(unit)

    first = await service.activate_ready_order(
        order_ref="ord_blocker_1",
        correlation_id="corr-blocker-1-first",
        idempotency_key="idem-blocker-1",
    )
    replay = await service.activate_ready_order(
        order_ref="ord_blocker_1",
        correlation_id="corr-blocker-1-replay",
        idempotency_key="idem-blocker-1",
    )

    assert replay.reason_code == "subscription_already_activated"
    assert replay.subscription_id == first.subscription_id
    assert replay.activation_id == first.activation_id
    assert unit.commit_count == 1
    assert len(unit.subscriptions.by_id) == 1
    assert len(unit.entitlement_activations.by_order) == 1
    assert len(unit.subscription_runtime.by_subscription) == 1
    _assert_cycle_matches_profile(unit, quota_profile)
    assert len(unit.commercial_audit.added) == 1
