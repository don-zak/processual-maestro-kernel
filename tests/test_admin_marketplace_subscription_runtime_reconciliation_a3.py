from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError
from processual_api.admin_marketplace.subscription_runtime_reconciliation_service import (
    apply_reconciliation_to_runtime_factory,
)


class Repo:
    def __init__(self, value=None):
        self.value = value
        self.added = []

    async def get_by_event_identity_hash(self, value, *, for_update=False):
        assert for_update is True
        return self.value

    async def get_by_decision_id(self, value, *, for_update=False):
        assert for_update is True
        return self.value

    async def get_by_subscription_id(self, value, *, for_update=False):
        assert for_update is True
        return self.value

    def add(self, value):
        self.added.append(value)


class Uow:
    def __init__(self, decision, runtime, transition=None):
        self.lemon_squeezy_reconciliation_decisions = Repo(decision)
        self.subscription_runtime = Repo(runtime)
        self.subscription_runtime_transitions = Repo(transition)
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commits += 1


def _decision(*, action="reconcile", customer_ref="customer-1"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        action=action,
        customer_ref=customer_ref,
    )


def _runtime(*, stage="active", customer_ref="customer-1"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        customer_ref=customer_ref,
        entitlement_profile_ref="ent-v1",
        quota_profile_ref="quota-v1",
        access_stage=stage,
        version=0,
        effective_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        grace_until=None,
        suspended_at=None,
        terminated_at=None,
    )


@pytest.mark.asyncio
async def test_payment_failure_enters_grace_and_commits_once() -> None:
    decision = _decision()
    runtime = _runtime()
    uow = Uow(decision, runtime)
    service = apply_reconciliation_to_runtime_factory(uow_factory=lambda: uow)
    effective_at = datetime(2026, 8, 5, tzinfo=timezone.utc)

    result = await service(
        reconciliation_event_identity_hash="a" * 64,
        subscription_id=runtime.subscription_id,
        customer_ref=runtime.customer_ref,
        event_name="subscription_payment_failed",
        effective_at=effective_at,
    )

    assert runtime.access_stage == "grace"
    assert runtime.grace_until == datetime(2026, 8, 12, tzinfo=timezone.utc)
    assert result.from_stage == "active"
    assert result.to_stage == "grace"
    assert uow.commits == 1
    assert uow.subscription_runtime_transitions.added == [result]


@pytest.mark.asyncio
async def test_terminal_event_terminates_runtime() -> None:
    decision = _decision()
    runtime = _runtime(stage="suspended")
    uow = Uow(decision, runtime)
    service = apply_reconciliation_to_runtime_factory(uow_factory=lambda: uow)

    result = await service(
        reconciliation_event_identity_hash="b" * 64,
        subscription_id=runtime.subscription_id,
        customer_ref=runtime.customer_ref,
        event_name="subscription_expired",
        effective_at=datetime(2026, 8, 6, tzinfo=timezone.utc),
    )

    assert runtime.access_stage == "terminated"
    assert runtime.terminated_at is not None
    assert result.to_stage == "terminated"


@pytest.mark.asyncio
async def test_exact_replay_is_read_only() -> None:
    decision = _decision()
    runtime = _runtime()
    existing = SimpleNamespace(
        subscription_id=runtime.subscription_id,
        customer_ref=runtime.customer_ref,
        event_name="subscription_payment_failed",
        to_stage="grace",
    )
    uow = Uow(decision, runtime, existing)
    service = apply_reconciliation_to_runtime_factory(uow_factory=lambda: uow)

    result = await service(
        reconciliation_event_identity_hash="c" * 64,
        subscription_id=runtime.subscription_id,
        customer_ref=runtime.customer_ref,
        event_name="subscription_payment_failed",
    )

    assert result is existing
    assert uow.commits == 0
    assert uow.subscription_runtime_transitions.added == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision_action,decision_customer,runtime_customer",
    [
        ("ignore", "customer-1", "customer-1"),
        ("requires_review", "customer-1", "customer-1"),
        ("reconcile", "customer-2", "customer-1"),
        ("reconcile", "customer-1", "customer-2"),
    ],
)
async def test_invalid_decision_or_binding_fails_without_commit(
    decision_action,
    decision_customer,
    runtime_customer,
) -> None:
    decision = _decision(action=decision_action, customer_ref=decision_customer)
    runtime = _runtime(customer_ref=runtime_customer)
    uow = Uow(decision, runtime)
    service = apply_reconciliation_to_runtime_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(
            reconciliation_event_identity_hash="d" * 64,
            subscription_id=runtime.subscription_id,
            customer_ref="customer-1",
            event_name="subscription_payment_success",
        )

    assert uow.commits == 0
    assert uow.subscription_runtime_transitions.added == []


@pytest.mark.asyncio
async def test_conflicting_replay_and_invalid_inputs_fail_closed() -> None:
    decision = _decision()
    runtime = _runtime()
    existing = SimpleNamespace(
        subscription_id=uuid.uuid4(),
        customer_ref=runtime.customer_ref,
        event_name="subscription_payment_failed",
        to_stage="grace",
    )
    uow = Uow(decision, runtime, existing)
    service = apply_reconciliation_to_runtime_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(
            reconciliation_event_identity_hash="e" * 64,
            subscription_id=runtime.subscription_id,
            customer_ref=runtime.customer_ref,
            event_name="subscription_payment_failed",
        )
    assert uow.commits == 0

    with pytest.raises(SubscriptionRuntimeError):
        await service(
            reconciliation_event_identity_hash="bad",
            subscription_id=runtime.subscription_id,
            customer_ref=runtime.customer_ref,
            event_name="subscription_payment_failed",
        )
