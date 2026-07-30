from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    AdminAdjustmentCommand,
    EntitlementGrantPostingInsufficientBalanceError,
    EntitlementGrantPostingService,
    MonthlySubscriptionGrantCommand,
    TopUpGrantCommand,
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


@pytest.mark.asyncio
async def test_real_postgresql_grant_posting_is_idempotent_and_atomic() -> None:
    engine = create_async_engine(_async_url(DATABASE_URL))
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def clear_rows() -> None:
        async with session_factory() as session:
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

    def uow_factory() -> SqlAlchemyEntitlementLedgerUnitOfWork:
        return SqlAlchemyEntitlementLedgerUnitOfWork(
            session_factory,
        )

    service = EntitlementGrantPostingService(
        uow_factory,
        entry_id_factory=uuid4,
    )

    await clear_rows()

    try:
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

        assert top_up.duplicate is False
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

        async with session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        "SELECT entry_type, units, idempotency_key "
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
            ).one()

        assert len(rows) == 2
        assert {row.entry_type for row in rows} == {
            "monthly_grant",
            "top_up_grant",
        }
        assert {row.idempotency_key for row in rows} == {
            "monthly:pg-gate:2026-07",
            "top-up:pg-gate-1",
        }
        assert sum(row.units for row in rows) == 7_000

        assert balance.available_units == 7_000
        assert balance.reserved_units == 0
        assert balance.committed_units == 0
        assert balance.version == 2
    finally:
        await clear_rows()
        await engine.dispose()
