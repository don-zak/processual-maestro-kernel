from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    AdminAdjustmentCommand,
    EntitlementGrantPostingConflictError,
    EntitlementGrantPostingInsufficientBalanceError,
    EntitlementGrantPostingService,
    MonthlySubscriptionGrantCommand,
    RefundReversalCommand,
    TopUpGrantCommand,
    UsageReversalCommand,
)
from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementLedgerEntry,
    LedgerEntryType,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapRequest,
    LedgerAppendRequest,
)
from processual_api.billing.commercial_entitlement_ledger_unit_of_work import (
    SqlAlchemyEntitlementLedgerUnitOfWork,
)

DATABASE_URL = os.environ.get(
    "PMK_ENTITLEMENT_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=("Set PMK_ENTITLEMENT_INTEGRATION_DATABASE_URL to run the PostgreSQL entitlement grant-posting gate."),
)

TENANT_ID = UUID("6b98dffe-2b26-4eeb-8a6b-4017ed56c901")
SUBSCRIPTION_ID = UUID("a8165e9d-57a8-4cc5-a874-2b9b910d67da")
NOW = datetime(2026, 7, 30, 14, 0, tzinfo=UTC)


def _async_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    return value


@pytest_asyncio.fixture
async def postgresql_gate():
    engine = create_async_engine(_async_url(DATABASE_URL))
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def clear_rows() -> None:
        async with session_factory() as session:
            await session.execute(
                text(
                    "DELETE FROM commercial_entitlement_reservation_locks "
                    "WHERE tenant_id = :tenant_id "
                    "AND subscription_id = :subscription_id"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                },
            )
            await session.execute(
                text(
                    "DELETE FROM commercial_entitlement_ledger_entries "
                    "WHERE tenant_id = :tenant_id "
                    "AND subscription_id = :subscription_id"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                },
            )
            await session.execute(
                text(
                    "DELETE FROM commercial_entitlement_balances "
                    "WHERE tenant_id = :tenant_id "
                    "AND subscription_id = :subscription_id"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                },
            )
            await session.commit()

    await clear_rows()

    try:
        yield engine, session_factory
    finally:
        await clear_rows()
        await engine.dispose()


def _service(session_factory) -> EntitlementGrantPostingService:
    return EntitlementGrantPostingService(
        lambda: SqlAlchemyEntitlementLedgerUnitOfWork(session_factory),
        entry_id_factory=uuid4,
    )


async def _persisted_state(session_factory):
    async with session_factory() as session:
        entries = (
            await session.execute(
                text(
                    "SELECT entry_id, entry_type, units, idempotency_key, "
                    "reservation_id, related_entry_id, adjustment_units "
                    "FROM commercial_entitlement_ledger_entries "
                    "WHERE tenant_id = :tenant_id "
                    "AND subscription_id = :subscription_id "
                    "ORDER BY occurred_at, entry_id"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                },
            )
        ).all()

        balance = (
            await session.execute(
                text(
                    "SELECT available_units, reserved_units, "
                    "committed_units, version "
                    "FROM commercial_entitlement_balances "
                    "WHERE tenant_id = :tenant_id "
                    "AND subscription_id = :subscription_id"
                ),
                {
                    "tenant_id": TENANT_ID,
                    "subscription_id": SUBSCRIPTION_ID,
                },
            )
        ).one_or_none()

    return entries, balance


@pytest.mark.asyncio
async def test_real_postgresql_grant_posting_is_idempotent_and_atomic(
    postgresql_gate,
) -> None:
    _, session_factory = postgresql_gate
    service = _service(session_factory)

    monthly = MonthlySubscriptionGrantCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        units=5_000,
        billing_cycle_reference="2026-07",
        plan_snapshot_reference="academic:v1",
        invoice_reference="invoice:pg-gate-1",
        idempotency_key="monthly:pg-gate:2026-07",
        occurred_at=NOW,
    )

    first = await service.post_monthly_subscription_grant(monthly)
    replay = await service.post_monthly_subscription_grant(monthly)

    assert first.duplicate is False
    assert first.available_units == 5_000
    assert first.resulting_balance_version == 1
    assert replay.duplicate is True
    assert replay.available_units == 5_000
    assert replay.resulting_balance_version == 1

    top_up = await service.post_top_up_grant(
        TopUpGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=2_000,
            order_reference="order:pg-gate-1",
            payment_evidence_reference="evidence:pg-gate-1",
            settlement_reference="settlement:pg-gate-1",
            idempotency_key="top-up:pg-gate-1",
            occurred_at=NOW,
        )
    )

    assert top_up.available_units == 7_000
    assert top_up.resulting_balance_version == 2

    with pytest.raises(
        EntitlementGrantPostingInsufficientBalanceError,
    ):
        await service.post_admin_adjustment(
            AdminAdjustmentCommand(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                adjustment_units=-7_001,
                actor_reference="platform-admin:pg-gate",
                authority_reference="platform_admin",
                audit_reference="audit:pg-gate-negative",
                reason="negative balance rejection proof",
                idempotency_key="admin-adjustment:pg-gate-negative",
                occurred_at=NOW,
            )
        )

    entries, balance = await _persisted_state(session_factory)

    assert len(entries) == 2
    assert {row.entry_type for row in entries} == {
        "monthly_grant",
        "top_up_grant",
    }
    assert sum(row.units for row in entries) == 7_000
    assert balance.available_units == 7_000
    assert balance.reserved_units == 0
    assert balance.committed_units == 0
    assert balance.version == 2


@pytest.mark.asyncio
async def test_real_postgresql_reversals_and_admin_adjustment_reconcile(
    postgresql_gate,
) -> None:
    _, session_factory = postgresql_gate
    service = _service(session_factory)

    monthly = await service.post_monthly_subscription_grant(
        MonthlySubscriptionGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=10_000,
            billing_cycle_reference="2026-08",
            plan_snapshot_reference="starter:v1",
            invoice_reference="invoice:pg-gate-2",
            idempotency_key="monthly:pg-gate:2026-08",
            occurred_at=NOW,
        )
    )

    refund = await service.post_refund_reversal(
        RefundReversalCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            related_entry_id=monthly.entry_id,
            units=1_500,
            refund_reference="refund:pg-gate-1",
            reason="partial subscription refund",
            idempotency_key="refund:pg-gate-1",
            occurred_at=NOW,
        )
    )
    assert refund.available_units == 8_500

    adjustment = await service.post_admin_adjustment(
        AdminAdjustmentCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            adjustment_units=250,
            actor_reference="platform-admin:pg-gate",
            authority_reference="platform_admin",
            audit_reference="audit:pg-gate-credit",
            reason="approved entitlement correction",
            idempotency_key="admin-adjustment:pg-gate-credit",
            occurred_at=NOW,
        )
    )
    assert adjustment.available_units == 8_750

    reservation_id = uuid4()
    commit_entry_id = uuid4()

    async with SqlAlchemyEntitlementLedgerUnitOfWork(
        session_factory,
    ) as unit:
        stored = await unit.balances.get_snapshot(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
        )
        assert stored is not None
        snapshot, version = stored

        commit_entry = EntitlementLedgerEntry(
            entry_id=commit_entry_id,
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            entry_type=LedgerEntryType.USAGE_COMMIT,
            units=1_000,
            idempotency_key="usage-commit:pg-gate-1",
            occurred_at=NOW,
            source_reference="usage-commit:pg-gate-1",
            reservation_id=reservation_id,
        )
        await unit.ledger.append(
            LedgerAppendRequest(
                entry=commit_entry,
                expected_balance_version=version,
            )
        )
        swap = await unit.balances.compare_and_swap(
            BalanceCompareAndSwapRequest(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                expected_version=version,
                available_units=snapshot.available_units,
                reserved_units=snapshot.reserved_units,
                committed_units=snapshot.committed_units + 1_000,
                calculated_at=NOW,
            )
        )
        assert swap.updated is True
        await unit.commit()

    usage_reversal = await service.post_usage_reversal(
        UsageReversalCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            related_entry_id=commit_entry_id,
            reservation_id=reservation_id,
            units=1_000,
            correction_reference="usage-correction:pg-gate-1",
            reason="usage commit reversal",
            idempotency_key="usage-reversal:pg-gate-1",
            occurred_at=NOW,
        )
    )

    assert usage_reversal.available_units == 9_750
    assert usage_reversal.committed_units == 0

    entries, balance = await _persisted_state(session_factory)
    signed_total = 0

    for row in entries:
        if row.entry_type in {
            "monthly_grant",
            "top_up_grant",
            "usage_reversal",
        }:
            signed_total += row.units
        elif row.entry_type == "refund_reversal":
            signed_total -= row.units
        elif row.entry_type == "admin_adjustment":
            signed_total += row.adjustment_units

    assert {row.entry_type for row in entries} == {
        "monthly_grant",
        "refund_reversal",
        "admin_adjustment",
        "usage_commit",
        "usage_reversal",
    }
    assert balance.available_units == 9_750
    assert balance.committed_units == 0
    assert balance.version == 5
    assert signed_total == balance.available_units


@pytest.mark.asyncio
async def test_real_postgresql_concurrent_cas_allows_one_winner(
    postgresql_gate,
) -> None:
    _, session_factory = postgresql_gate
    service = _service(session_factory)

    await service.post_monthly_subscription_grant(
        MonthlySubscriptionGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=1_000,
            billing_cycle_reference="2026-09",
            plan_snapshot_reference="starter:v1",
            invoice_reference="invoice:pg-concurrency",
            idempotency_key="monthly:pg-concurrency",
            occurred_at=NOW,
        )
    )

    barrier = asyncio.Barrier(2)

    async def contender(
        *,
        entry_id: UUID,
        idempotency_key: str,
    ):
        async with SqlAlchemyEntitlementLedgerUnitOfWork(
            session_factory,
        ) as unit:
            stored = await unit.balances.get_snapshot(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
            )
            assert stored is not None
            snapshot, version = stored
            await barrier.wait()

            entry = EntitlementLedgerEntry(
                entry_id=entry_id,
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                entry_type=LedgerEntryType.TOP_UP_GRANT,
                units=100,
                idempotency_key=idempotency_key,
                occurred_at=NOW,
                source_reference=idempotency_key,
            )

            try:
                await unit.ledger.append(
                    LedgerAppendRequest(
                        entry=entry,
                        expected_balance_version=version,
                    )
                )
                result = await unit.balances.compare_and_swap(
                    BalanceCompareAndSwapRequest(
                        tenant_id=TENANT_ID,
                        subscription_id=SUBSCRIPTION_ID,
                        expected_version=version,
                        available_units=snapshot.available_units + 100,
                        reserved_units=snapshot.reserved_units,
                        committed_units=snapshot.committed_units,
                        calculated_at=NOW,
                    )
                )
                if not result.updated:
                    raise EntitlementGrantPostingConflictError("entitlement balance compare-and-swap conflict")
                await unit.commit()
                return "committed"
            except BaseException:
                await unit.rollback()
                return "rolled_back"

    outcomes = await asyncio.gather(
        contender(
            entry_id=uuid4(),
            idempotency_key="top-up:pg-concurrency:a",
        ),
        contender(
            entry_id=uuid4(),
            idempotency_key="top-up:pg-concurrency:b",
        ),
    )

    assert sorted(outcomes) == ["committed", "rolled_back"]

    entries, balance = await _persisted_state(session_factory)
    top_up_entries = [row for row in entries if row.entry_type == "top_up_grant"]

    assert len(top_up_entries) == 1
    assert balance.available_units == 1_100
    assert balance.version == 2
