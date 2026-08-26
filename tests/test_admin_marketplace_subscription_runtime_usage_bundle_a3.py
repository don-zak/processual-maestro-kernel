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
