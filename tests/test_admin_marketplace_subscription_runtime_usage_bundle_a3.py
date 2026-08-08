from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionQuotaAccountState,
    SubscriptionRuntimeError,
    SubscriptionRuntimeState,
    build_usage_reservation,
    reserve_quota_units,
    transition_subscription_runtime,
)
from processual_api.admin_marketplace.subscription_usage_service import (
    record_subscription_usage_factory,
)


NOW = datetime(2026, 8, 5, 20, 0, tzinfo=timezone.utc)


def test_runtime_transitions_are_fail_closed_and_non_mutating() -> None:
    state = SubscriptionRuntimeState(
        subscription_id=uuid.uuid4(),
        customer_ref="customer-1",
        entitlement_profile_ref="entitlements-pro",
        quota_profile_ref="quota-pro",
        access_stage="active",
        version=0,
        effective_at=NOW,
    )
    before = deepcopy(state)
    with pytest.raises(SubscriptionRuntimeError):
        transition_subscription_runtime(
            state,
            target_stage="grace",
            effective_at=NOW,
            grace_until=NOW,
        )
    assert state == before

    transition_subscription_runtime(
        state,
        target_stage="grace",
        effective_at=NOW,
        grace_until=NOW + timedelta(days=7),
    )
    assert state.access_stage == "grace"
    assert state.version == 1

    before = deepcopy(state)
    with pytest.raises(SubscriptionRuntimeError):
        transition_subscription_runtime(
            state,
            target_stage="terminated",
            effective_at=NOW - timedelta(seconds=1),
        )
    assert state == before


def test_terminated_runtime_cannot_be_reactivated() -> None:
    state = SubscriptionRuntimeState(
        subscription_id=uuid.uuid4(),
        customer_ref="customer-1",
        entitlement_profile_ref="entitlements-pro",
        quota_profile_ref="quota-pro",
        access_stage="terminated",
        version=3,
        effective_at=NOW,
        terminated_at=NOW,
    )
    before = deepcopy(state)
    with pytest.raises(SubscriptionRuntimeError):
        transition_subscription_runtime(
            state,
            target_stage="active",
            effective_at=NOW + timedelta(seconds=1),
        )
    assert state == before


def test_quota_reservation_enforces_period_and_limit_without_partial_mutation() -> None:
    account = SubscriptionQuotaAccountState(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        customer_ref="customer-1",
        quota_profile_ref="quota-pro",
        metric_code="workflow_runs",
        period_start=NOW,
        period_end=NOW + timedelta(days=30),
        limit_units=10,
        used_units=8,
        version=2,
    )
    too_large = build_usage_reservation(
        units=3,
        idempotency_key="usage-1",
        dimensions={"workflow": "wf-1"},
        occurred_at=NOW + timedelta(seconds=1),
    )
    before = deepcopy(account)
    with pytest.raises(SubscriptionRuntimeError):
        reserve_quota_units(account, reservation=too_large)
    assert account == before

    outside = build_usage_reservation(
        units=1,
        idempotency_key="usage-2",
        dimensions={},
        occurred_at=account.period_end,
    )
    with pytest.raises(SubscriptionRuntimeError):
        reserve_quota_units(account, reservation=outside)
    assert account == before


def test_usage_reservation_hashes_are_stable_and_reject_invalid_values() -> None:
    first = build_usage_reservation(
        units=2,
        idempotency_key="  request-1  ",
        dimensions={"b": 2, "a": 1},
        occurred_at=NOW,
    )
    second = build_usage_reservation(
        units=2,
        idempotency_key="request-1",
        dimensions={"a": 1, "b": 2},
        occurred_at=NOW,
    )
    assert first.idempotency_key_hash == second.idempotency_key_hash
    assert first.dimensions_digest == second.dimensions_digest

    for invalid_units in (0, -1):
        with pytest.raises(SubscriptionRuntimeError):
            build_usage_reservation(
                units=invalid_units,
                idempotency_key="request",
                dimensions={},
                occurred_at=NOW,
            )


class Repo:
    def __init__(self, value=None) -> None:
        self.value = value
        self.added = []

    async def get_by_idempotency_hash(self, value, *, for_update=False):
        assert for_update is True
        return self.value

    async def get_by_subscription_id(self, value, *, for_update=False):
        assert for_update is True
        return self.value

    async def get_current(self, **kwargs):
        assert kwargs["for_update"] is True
        return self.value

    def add(self, value) -> None:
        self.added.append(value)


class Uow:
    def __init__(self, *, runtime, quota, usage=None) -> None:
        self.subscription_runtime = Repo(runtime)
        self.subscription_quotas = Repo(quota)
        self.subscription_usage = Repo(usage)
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def _runtime(stage="active"):
    return type(
        "Runtime",
        (),
        {
            "subscription_id": SUBSCRIPTION_ID,
            "customer_ref": "customer-1",
            "quota_profile_ref": "quota-pro",
            "access_stage": stage,
        },
    )()


def _quota():
    return type(
        "Quota",
        (),
        {
            "id": uuid.uuid4(),
            "subscription_id": SUBSCRIPTION_ID,
            "customer_ref": "customer-1",
            "quota_profile_ref": "quota-pro",
            "metric_code": "workflow_runs",
            "period_start": NOW,
            "period_end": NOW + timedelta(days=30),
            "limit_units": 10,
            "used_units": 4,
            "version": 1,
        },
    )()


SUBSCRIPTION_ID = uuid.uuid4()


@pytest.mark.asyncio
async def test_usage_service_records_once_with_locked_bindings_and_single_commit() -> None:
    uow = Uow(runtime=_runtime(), quota=_quota())
    service = record_subscription_usage_factory(uow_factory=lambda: uow)

    usage = await service(
        subscription_id=SUBSCRIPTION_ID,
        customer_ref="customer-1",
        metric_code="workflow_runs",
        units=2,
        idempotency_key="request-1",
        dimensions={"workflow": "wf-1"},
        occurred_at=NOW + timedelta(seconds=1),
    )

    assert uow.subscription_quotas.value.used_units == 6
    assert uow.subscription_quotas.value.version == 2
    assert uow.subscription_usage.added == [usage]
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_usage_service_replay_is_idempotent_and_conflicts_fail_closed() -> None:
    existing = type(
        "Usage",
        (),
        {
            "subscription_id": SUBSCRIPTION_ID,
            "customer_ref": "customer-1",
            "metric_code": "workflow_runs",
            "units": 2,
            "dimensions_digest": build_usage_reservation(
                units=2,
                idempotency_key="request-1",
                dimensions={"workflow": "wf-1"},
                occurred_at=NOW,
            ).dimensions_digest,
        },
    )()
    uow = Uow(runtime=_runtime(), quota=_quota(), usage=existing)
    service = record_subscription_usage_factory(uow_factory=lambda: uow)

    result = await service(
        subscription_id=SUBSCRIPTION_ID,
        customer_ref="customer-1",
        metric_code="workflow_runs",
        units=2,
        idempotency_key="request-1",
        dimensions={"workflow": "wf-1"},
        occurred_at=NOW,
    )
    assert result is existing
    assert uow.commits == 0

    with pytest.raises(SubscriptionRuntimeError):
        await service(
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            metric_code="workflow_runs",
            units=3,
            idempotency_key="request-1",
            dimensions={"workflow": "wf-1"},
            occurred_at=NOW,
        )
    assert uow.commits == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["suspended", "terminated"])
async def test_usage_service_blocks_non_consuming_stages_without_quota_mutation(stage) -> None:
    quota = _quota()
    before = (quota.used_units, quota.version)
    uow = Uow(runtime=_runtime(stage), quota=quota)
    service = record_subscription_usage_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            metric_code="workflow_runs",
            units=1,
            idempotency_key=f"request-{stage}",
            dimensions={},
            occurred_at=NOW,
        )

    assert (quota.used_units, quota.version) == before
    assert uow.subscription_usage.added == []
    assert uow.commits == 0


@pytest.mark.asyncio
async def test_usage_service_rejects_cross_customer_and_profile_binding() -> None:
    quota = _quota()
    quota.quota_profile_ref = "quota-other"
    uow = Uow(runtime=_runtime(), quota=quota)
    service = record_subscription_usage_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(
            subscription_id=SUBSCRIPTION_ID,
            customer_ref="customer-1",
            metric_code="workflow_runs",
            units=1,
            idempotency_key="request-binding",
            dimensions={},
            occurred_at=NOW,
        )
    assert uow.commits == 0
