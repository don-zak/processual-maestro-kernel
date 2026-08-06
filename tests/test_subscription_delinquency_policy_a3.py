from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_delinquency_policy import (
    GRACE_DAYS,
    apply_payment_failure,
    resolve_payment_delinquency,
)

SUBSCRIPTION_ID = uuid.uuid4()
CUSTOMER_REF = "customer_001"
NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


class DelinquencyRepository:
    def __init__(self) -> None:
        self.value = None
        self.added: list[object] = []

    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        if self.value is None or self.value.subscription_id != subscription_id:
            return None
        return self.value

    def add(self, value: object) -> None:
        self.value = value
        self.added.append(value)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.subscription_delinquency = DelinquencyRepository()


def _subscription() -> SimpleNamespace:
    return SimpleNamespace(id=SUBSCRIPTION_ID, customer_ref=CUSTOMER_REF)


@pytest.mark.asyncio
async def test_first_failure_starts_fifteen_day_degraded_grace() -> None:
    uow = FakeUnitOfWork()

    record = await apply_payment_failure(
        uow=uow,
        subscription=_subscription(),
        effective_at=NOW,
    )

    assert record.state == "grace_degraded"
    assert record.missed_billing_cycles == 1
    assert record.grace_until == NOW + timedelta(days=GRACE_DAYS)
    assert record.grace_usage_percent == 25


@pytest.mark.asyncio
async def test_repeated_failure_in_same_month_is_idempotent_for_cycle_count() -> None:
    uow = FakeUnitOfWork()
    subscription = _subscription()
    await apply_payment_failure(
        uow=uow,
        subscription=subscription,
        effective_at=NOW,
    )

    record = await apply_payment_failure(
        uow=uow,
        subscription=subscription,
        effective_at=NOW + timedelta(days=3),
    )

    assert record.missed_billing_cycles == 1
    assert record.last_failed_cycle_key == "2026-08"


@pytest.mark.asyncio
async def test_third_missed_cycle_freezes_account() -> None:
    uow = FakeUnitOfWork()
    subscription = _subscription()
    for month in (8, 9, 10):
        record = await apply_payment_failure(
            uow=uow,
            subscription=subscription,
            effective_at=datetime(2026, month, 6, tzinfo=UTC),
        )

    assert record.missed_billing_cycles == 3
    assert record.state == "account_frozen"
    assert record.frozen_at == datetime(2026, 10, 6, tzinfo=UTC)
    assert record.grace_until is None


@pytest.mark.asyncio
async def test_sixth_missed_cycle_marks_pending_deletion() -> None:
    uow = FakeUnitOfWork()
    subscription = _subscription()
    dates = [
        datetime(2026, 8, 6, tzinfo=UTC),
        datetime(2026, 9, 6, tzinfo=UTC),
        datetime(2026, 10, 6, tzinfo=UTC),
        datetime(2026, 11, 6, tzinfo=UTC),
        datetime(2026, 12, 6, tzinfo=UTC),
        datetime(2027, 1, 6, tzinfo=UTC),
    ]
    for value in dates:
        record = await apply_payment_failure(
            uow=uow,
            subscription=subscription,
            effective_at=value,
        )

    assert record.missed_billing_cycles == 6
    assert record.state == "pending_deletion"
    assert record.deletion_eligible_at == dates[-1]


@pytest.mark.asyncio
async def test_payment_recovery_resolves_delinquency_without_deleting_history() -> None:
    uow = FakeUnitOfWork()
    subscription = _subscription()
    await apply_payment_failure(
        uow=uow,
        subscription=subscription,
        effective_at=NOW,
    )

    record = await resolve_payment_delinquency(
        uow=uow,
        subscription=subscription,
        effective_at=NOW + timedelta(days=7),
    )

    assert record is not None
    assert record.state == "resolved"
    assert record.missed_billing_cycles == 0
    assert record.resolved_at == NOW + timedelta(days=7)
    assert record.first_failed_at == NOW
