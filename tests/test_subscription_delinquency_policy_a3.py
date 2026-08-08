from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_delinquency_policy import (
    GRACE_DAYS,
    apply_payment_failure,
    resolve_payment_delinquency,
    rollover_payment_deadline,
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


class QuotaCycleRepository:
    def __init__(self, cycles: list[object] | None = None) -> None:
        self.cycles = cycles or []

    async def list_rollover_cycles(
        self,
        *,
        subscription_id: uuid.UUID,
        for_update: bool = False,
    ) -> list[object]:
        return [
            cycle
            for cycle in self.cycles
            if cycle.subscription_id == subscription_id
            and cycle.rollover_units > 0
            and cycle.rollover_status != "expired"
        ]


class FakeUnitOfWork:
    def __init__(self, cycles: list[object] | None = None) -> None:
        self.subscription_delinquency = DelinquencyRepository()
        self.subscription_quota_cycles = QuotaCycleRepository(cycles)


def _subscription() -> SimpleNamespace:
    return SimpleNamespace(id=SUBSCRIPTION_ID, customer_ref=CUSTOMER_REF)


def _rollover_cycle(**overrides: object) -> SimpleNamespace:
    values = {
        "subscription_id": SUBSCRIPTION_ID,
        "rollover_units": 40,
        "rollover_status": "available",
        "rollover_expires_at": None,
        "rollover_locked_at": None,
        "rollover_restored_at": None,
        "rollover_expired_at": None,
        "version": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_first_failure_starts_fifteen_day_degraded_grace() -> None:
    cycle = _rollover_cycle()
    uow = FakeUnitOfWork([cycle])

    record = await apply_payment_failure(
        uow=uow,
        subscription=_subscription(),
        effective_at=NOW,
    )

    assert record.state == "grace_degraded"
    assert record.missed_billing_cycles == 1
    assert record.grace_until == NOW + timedelta(days=GRACE_DAYS)
    assert record.grace_usage_percent == 25
    assert cycle.rollover_status == "locked_for_delinquency"
    assert cycle.rollover_units == 40
    assert cycle.rollover_expires_at == datetime(2026, 10, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_repeated_failure_in_same_month_is_idempotent_for_cycle_count() -> None:
    cycle = _rollover_cycle()
    uow = FakeUnitOfWork([cycle])
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
    assert cycle.version == 1


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
async def test_payment_recovery_restores_rollover_before_deadline() -> None:
    cycle = _rollover_cycle()
    uow = FakeUnitOfWork([cycle])
    subscription = _subscription()
    await apply_payment_failure(
        uow=uow,
        subscription=subscription,
        effective_at=NOW,
    )

    paid_at = datetime(2026, 9, 30, 23, 59, tzinfo=UTC)
    record = await resolve_payment_delinquency(
        uow=uow,
        subscription=subscription,
        effective_at=paid_at,
    )

    assert record is not None
    assert record.state == "resolved"
    assert record.missed_billing_cycles == 0
    assert record.resolved_at == paid_at
    assert record.first_failed_at == NOW
    assert cycle.rollover_status == "restored"
    assert cycle.rollover_units == 40
    assert cycle.rollover_restored_at == paid_at


@pytest.mark.asyncio
async def test_payment_at_deadline_expires_rollover_without_erasing_audit_value() -> None:
    cycle = _rollover_cycle()
    uow = FakeUnitOfWork([cycle])
    subscription = _subscription()
    await apply_payment_failure(
        uow=uow,
        subscription=subscription,
        effective_at=NOW,
    )

    paid_at = rollover_payment_deadline(NOW)
    record = await resolve_payment_delinquency(
        uow=uow,
        subscription=subscription,
        effective_at=paid_at,
    )

    assert record is not None
    assert record.state == "resolved"
    assert cycle.rollover_status == "expired"
    assert cycle.rollover_units == 40
    assert cycle.rollover_expired_at == paid_at
