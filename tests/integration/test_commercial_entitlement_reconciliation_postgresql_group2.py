from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    EntitlementGrantPostingService,
    MonthlySubscriptionGrantCommand,
    TopUpGrantCommand,
)
from processual_api.billing.commercial_entitlement_ledger_models import (
    CommercialEntitlementBalance,
    CommercialEntitlementLedgerEntry,
)
from processual_api.billing.commercial_entitlement_ledger_unit_of_work import (
    SqlAlchemyEntitlementLedgerUnitOfWork,
)
from processual_api.billing.commercial_entitlement_reconciliation_service import (
    EntitlementReconciliationOutcome,
    EntitlementReconciliationPolicy,
    EntitlementReconciliationService,
    ReconcileEntitlementCommand,
)

DATABASE_URL = os.environ.get(
    "PMK_ENTITLEMENT_RECONCILIATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=("Set PMK_ENTITLEMENT_RECONCILIATION_DATABASE_URL to run the PostgreSQL reconciliation gate."),
)

TENANT_ID = UUID("a3d73d30-9ee7-49dc-b11d-4075c12d8101")
SUBSCRIPTION_ID = UUID("a3d73d30-9ee7-49dc-b11d-4075c12d8102")
NOW = datetime(2026, 7, 30, 15, 30, tzinfo=UTC)


def _async_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    return value


@pytest_asyncio.fixture
async def postgresql_reconciliation_gate():
    engine = create_async_engine(_async_url(DATABASE_URL))
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def clear_rows() -> None:
        async with session_factory() as session:
            await session.execute(
                delete(CommercialEntitlementLedgerEntry).where(
                    CommercialEntitlementLedgerEntry.tenant_id == TENANT_ID,
                    CommercialEntitlementLedgerEntry.subscription_id == SUBSCRIPTION_ID,
                )
            )
            await session.execute(
                delete(CommercialEntitlementBalance).where(
                    CommercialEntitlementBalance.tenant_id == TENANT_ID,
                    CommercialEntitlementBalance.subscription_id == SUBSCRIPTION_ID,
                )
            )
            await session.commit()

    await clear_rows()

    try:
        yield session_factory
    finally:
        await clear_rows()
        await engine.dispose()


def _posting_service(session_factory) -> EntitlementGrantPostingService:
    return EntitlementGrantPostingService(
        lambda: SqlAlchemyEntitlementLedgerUnitOfWork(session_factory),
        entry_id_factory=uuid4,
    )


def _reconciliation_service(
    session_factory,
) -> EntitlementReconciliationService:
    return EntitlementReconciliationService(
        unit_of_work_factory=lambda: SqlAlchemyEntitlementLedgerUnitOfWork(session_factory),
        policy=EntitlementReconciliationPolicy(
            enabled=True,
            page_size=1,
        ),
    )


def _command(audit_reference: str) -> ReconcileEntitlementCommand:
    return ReconcileEntitlementCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        requested_at=NOW,
        actor_reference="reconciliation-worker:postgresql-gate",
        audit_reference=audit_reference,
    )


async def _entry_count(session_factory) -> int:
    async with session_factory() as session:
        return len(
            (
                await session.scalars(
                    select(CommercialEntitlementLedgerEntry).where(
                        CommercialEntitlementLedgerEntry.tenant_id == TENANT_ID,
                        CommercialEntitlementLedgerEntry.subscription_id == SUBSCRIPTION_ID,
                    )
                )
            ).all()
        )


@pytest.mark.asyncio
async def test_postgresql_reconciliation_reports_all_states_read_only(
    postgresql_reconciliation_gate,
) -> None:
    session_factory = postgresql_reconciliation_gate
    posting = _posting_service(session_factory)
    reconciliation = _reconciliation_service(session_factory)

    await posting.post_monthly_subscription_grant(
        MonthlySubscriptionGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=5_000,
            billing_cycle_reference="2026-07",
            plan_snapshot_reference="academic:v1",
            invoice_reference="activation-invoice:2026-07",
            idempotency_key="reconciliation-monthly:2026-07",
            occurred_at=NOW,
        )
    )
    await posting.post_top_up_grant(
        TopUpGrantCommand(
            tenant_id=TENANT_ID,
            subscription_id=SUBSCRIPTION_ID,
            units=2_000,
            order_reference="reconciliation-order-1",
            payment_evidence_reference="evidence://reconciliation/1",
            settlement_reference="settlement://reconciliation/1",
            idempotency_key="reconciliation-top-up:1",
            occurred_at=NOW,
        )
    )

    before_count = await _entry_count(session_factory)
    assert before_count == 2

    matched = await reconciliation.reconcile(_command("reconciliation-audit:match"))
    assert matched.outcome is EntitlementReconciliationOutcome.MATCH
    assert matched.expected_available_units == 7_000
    assert matched.actual_available_units == 7_000
    assert matched.available_delta == 0
    assert matched.auto_repair_performed is False
    assert await _entry_count(session_factory) == before_count

    async with session_factory() as session:
        await session.execute(
            update(CommercialEntitlementBalance)
            .where(
                CommercialEntitlementBalance.tenant_id == TENANT_ID,
                CommercialEntitlementBalance.subscription_id == SUBSCRIPTION_ID,
            )
            .values(available_units=6_990)
        )
        await session.commit()

    mismatched = await reconciliation.reconcile(_command("reconciliation-audit:mismatch"))
    assert mismatched.outcome is EntitlementReconciliationOutcome.MISMATCH
    assert mismatched.expected_available_units == 7_000
    assert mismatched.actual_available_units == 6_990
    assert mismatched.available_delta == -10
    assert mismatched.auto_repair_performed is False
    assert await _entry_count(session_factory) == before_count

    async with session_factory() as session:
        await session.execute(
            delete(CommercialEntitlementBalance).where(
                CommercialEntitlementBalance.tenant_id == TENANT_ID,
                CommercialEntitlementBalance.subscription_id == SUBSCRIPTION_ID,
            )
        )
        await session.commit()

    missing = await reconciliation.reconcile(_command("reconciliation-audit:missing"))
    assert missing.outcome is EntitlementReconciliationOutcome.MISSING_BALANCE
    assert missing.expected_available_units == 7_000
    assert missing.actual_available_units is None
    assert missing.available_delta is None
    assert missing.auto_repair_performed is False
    assert await _entry_count(session_factory) == before_count
