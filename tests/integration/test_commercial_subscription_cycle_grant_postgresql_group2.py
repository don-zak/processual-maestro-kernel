from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_entitlement_ledger_models import (
    CommercialEntitlementBalance,
    CommercialEntitlementLedgerEntry,
)
from processual_api.billing.commercial_entitlement_ledger_unit_of_work import (
    SqlAlchemyEntitlementLedgerUnitOfWork,
)
from processual_api.billing.commercial_subscription_cycle_grant_service import (
    ApprovedSubscriptionCycleGrantCommand,
    CommercialSubscriptionCycleGrantService,
    SubscriptionCycleGrantPolicy,
    SubscriptionCycleKind,
)

DATABASE_URL = os.environ.get(
    "PMK_SUBSCRIPTION_CYCLE_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=("Set PMK_SUBSCRIPTION_CYCLE_INTEGRATION_DATABASE_URL to run the PostgreSQL subscription-cycle gate."),
)

TENANT_ID = UUID("3f11f5a7-8c34-40e0-a941-8cb7f8eb4701")
SUBSCRIPTION_ID = UUID("3f11f5a7-8c34-40e0-a941-8cb7f8eb4702")
JULY_START = datetime(2026, 7, 1, tzinfo=UTC)
AUGUST_START = datetime(2026, 8, 1, tzinfo=UTC)
SEPTEMBER_START = datetime(2026, 9, 1, tzinfo=UTC)


def _async_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    return value


@pytest_asyncio.fixture
async def postgresql_cycle_gate():
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


def _service(session_factory) -> CommercialSubscriptionCycleGrantService:
    return CommercialSubscriptionCycleGrantService(
        unit_of_work_factory=lambda: SqlAlchemyEntitlementLedgerUnitOfWork(session_factory),
        policy=SubscriptionCycleGrantPolicy(
            enabled=True,
            writes_enabled=True,
        ),
        entry_id_factory=uuid4,
    )


def _command(
    *,
    kind: SubscriptionCycleKind,
    cycle_reference: str,
    started_at: datetime,
    ends_at: datetime,
) -> ApprovedSubscriptionCycleGrantCommand:
    invoice_prefix = "activation-invoice" if kind is SubscriptionCycleKind.ACTIVATION else "renewal-invoice"
    return ApprovedSubscriptionCycleGrantCommand(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        cycle_kind=kind,
        cycle_reference=cycle_reference,
        cycle_started_at=started_at,
        cycle_ends_at=ends_at,
        units=5_000,
        plan_snapshot_reference="academic:v1",
        invoice_reference=(f"{invoice_prefix}:{cycle_reference}"),
        authority_reference=("subscription-billing-authority:postgresql-gate"),
        approval_reference=(f"billing-cycle-approval:{cycle_reference}"),
        approved_by="billing-authority:postgresql-gate",
        occurred_at=started_at,
    )


@pytest.mark.asyncio
async def test_postgresql_activation_replay_renewal_preserve_rollover(
    postgresql_cycle_gate,
) -> None:
    session_factory = postgresql_cycle_gate

    async with session_factory() as session:
        session.add(
            CommercialEntitlementBalance(
                tenant_id=TENANT_ID,
                subscription_id=SUBSCRIPTION_ID,
                available_units=750,
                reserved_units=0,
                committed_units=0,
                version=0,
                calculated_at=JULY_START,
            )
        )
        await session.commit()

    service = _service(session_factory)

    activation = await service.post_approved_cycle(
        _command(
            kind=SubscriptionCycleKind.ACTIVATION,
            cycle_reference="2026-07",
            started_at=JULY_START,
            ends_at=AUGUST_START,
        )
    )
    replay = await service.post_approved_cycle(
        _command(
            kind=SubscriptionCycleKind.ACTIVATION,
            cycle_reference="2026-07",
            started_at=JULY_START,
            ends_at=AUGUST_START,
        )
    )
    renewal = await service.post_approved_cycle(
        _command(
            kind=SubscriptionCycleKind.RENEWAL,
            cycle_reference="2026-08",
            started_at=AUGUST_START,
            ends_at=SEPTEMBER_START,
        )
    )

    assert activation.committed is True
    assert activation.duplicate is False
    assert activation.ledger_result.available_units == 5_750
    assert activation.ledger_result.resulting_balance_version == 1

    assert replay.committed is False
    assert replay.duplicate is True
    assert replay.ledger_result.available_units == 5_750
    assert replay.ledger_result.resulting_balance_version == 1

    assert renewal.committed is True
    assert renewal.duplicate is False
    assert renewal.ledger_result.available_units == 10_750
    assert renewal.ledger_result.resulting_balance_version == 2

    async with session_factory() as session:
        entries = (
            await session.scalars(
                select(CommercialEntitlementLedgerEntry)
                .where(
                    CommercialEntitlementLedgerEntry.tenant_id == TENANT_ID,
                    CommercialEntitlementLedgerEntry.subscription_id == SUBSCRIPTION_ID,
                )
                .order_by(
                    CommercialEntitlementLedgerEntry.occurred_at,
                    CommercialEntitlementLedgerEntry.entry_id,
                )
            )
        ).all()
        balance = await session.get(
            CommercialEntitlementBalance,
            {
                "tenant_id": TENANT_ID,
                "subscription_id": SUBSCRIPTION_ID,
            },
        )

    assert len(entries) == 2
    assert [entry.entry_type for entry in entries] == [
        "monthly_grant",
        "monthly_grant",
    ]
    assert [entry.units for entry in entries] == [5_000, 5_000]
    assert entries[0].idempotency_key.endswith(":2026-07")
    assert entries[1].idempotency_key.endswith(":2026-08")

    assert balance is not None
    assert balance.available_units == 10_750
    assert balance.reserved_units == 0
    assert balance.committed_units == 0
    assert balance.version == 2
