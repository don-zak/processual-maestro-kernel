from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_entitlement_ledger_models import (
    CommercialEntitlementBalance,
    CommercialEntitlementLedgerEntry,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapResult,
)
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_entitlement_bridge import (
    CommercialTopUpEntitlementBridgeService,
    PostApprovedTopUpCommand,
    TopUpEntitlementBridgePolicy,
)
from processual_api.billing.commercial_top_up_entitlement_unit_of_work import (
    SqlAlchemyAtomicTopUpEntitlementUnitOfWork,
)
from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpAuditRecord,
    CommercialTopUpGrant,
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)

DATABASE_URL = os.environ.get(
    "PMK_TOP_UP_ENTITLEMENT_INTEGRATION_DATABASE_URL",
    "",
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason=("Set PMK_TOP_UP_ENTITLEMENT_INTEGRATION_DATABASE_URL to run the PostgreSQL atomic bridge gate."),
)

TENANT_ID = UUID("81ff9160-232b-45bb-a6c1-3faeea551801")
ACCOUNT_ID = UUID("81ff9160-232b-45bb-a6c1-3faeea551802")
SUBSCRIPTION_ID = UUID("81ff9160-232b-45bb-a6c1-3faeea551803")
ORDER_ID = UUID("81ff9160-232b-45bb-a6c1-3faeea551804")
NOW = datetime(2026, 7, 30, 14, 40, tzinfo=UTC)


def _async_url(value: str) -> str:
    if value.startswith("postgresql://"):
        return value.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    return value


@pytest_asyncio.fixture
async def postgresql_bridge_gate():
    engine = create_async_engine(_async_url(DATABASE_URL))
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async def clear_rows() -> None:
        async with session_factory() as session:
            await session.execute(
                delete(CommercialTopUpAuditRecord).where(CommercialTopUpAuditRecord.order_id == ORDER_ID)
            )
            await session.execute(delete(CommercialTopUpGrant).where(CommercialTopUpGrant.order_id == ORDER_ID))
            await session.execute(
                delete(CommercialTopUpPaymentEvidence).where(CommercialTopUpPaymentEvidence.order_id == ORDER_ID)
            )
            await session.execute(delete(CommercialTopUpOrder).where(CommercialTopUpOrder.id == ORDER_ID))
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


async def _seed_order(session_factory) -> None:
    async with session_factory() as session:
        session.add(
            CommercialTopUpOrder(
                id=ORDER_ID,
                account_id=ACCOUNT_ID,
                subscription_id=SUBSCRIPTION_ID,
                plan_code="starter",
                requested_units=2_000,
                bundle_count=2,
                total_price_usd=Decimal("118.00"),
                settlement_currency="USD",
                settlement_amount=Decimal("118.00"),
                channel=TopUpCheckoutChannel.LEMON_SQUEEZY.value,
                idempotency_key="pg-bridge-order-1",
                state="awaiting_payment",
            )
        )
        await session.commit()


def _command() -> PostApprovedTopUpCommand:
    return PostApprovedTopUpCommand(
        tenant_id=TENANT_ID,
        order_id=ORDER_ID,
        provider_reference="pg-bridge-provider-payment-1",
        verified_amount=Decimal("118.00"),
        verified_currency="USD",
        immutable_evidence_reference="evidence://pg-bridge/1",
        settlement_reference="settlement://pg-bridge/1",
        actor_reference="payment-verifier:pg-bridge",
        occurred_at=NOW,
    )


def _service(session_factory, *, uow_type=SqlAlchemyAtomicTopUpEntitlementUnitOfWork):
    return CommercialTopUpEntitlementBridgeService(
        unit_of_work_factory=lambda: uow_type(session_factory),
        policy=TopUpEntitlementBridgePolicy(
            enabled=True,
            writes_enabled=True,
        ),
        entry_id_factory=uuid4,
    )


async def _counts_and_state(session_factory):
    async with session_factory() as session:
        order = await session.get(CommercialTopUpOrder, ORDER_ID)
        payments = (
            await session.scalars(
                select(CommercialTopUpPaymentEvidence).where(CommercialTopUpPaymentEvidence.order_id == ORDER_ID)
            )
        ).all()
        grants = (
            await session.scalars(select(CommercialTopUpGrant).where(CommercialTopUpGrant.order_id == ORDER_ID))
        ).all()
        audits = (
            await session.scalars(
                select(CommercialTopUpAuditRecord).where(CommercialTopUpAuditRecord.order_id == ORDER_ID)
            )
        ).all()
        entries = (
            await session.scalars(
                select(CommercialEntitlementLedgerEntry).where(
                    CommercialEntitlementLedgerEntry.tenant_id == TENANT_ID,
                    CommercialEntitlementLedgerEntry.subscription_id == SUBSCRIPTION_ID,
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

    return order, payments, grants, audits, entries, balance


@pytest.mark.asyncio
async def test_postgresql_bridge_commits_all_surfaces_and_replays_once(
    postgresql_bridge_gate,
) -> None:
    session_factory = postgresql_bridge_gate
    await _seed_order(session_factory)
    service = _service(session_factory)

    first = await service.post_approved_top_up(_command())
    replay = await service.post_approved_top_up(_command())

    assert first.committed is True
    assert first.duplicate is False
    assert first.available_units == 2_000
    assert first.resulting_balance_version == 1
    assert replay.committed is False
    assert replay.duplicate is True
    assert replay.ledger_entry_id == first.ledger_entry_id

    order, payments, grants, audits, entries, balance = await _counts_and_state(session_factory)

    assert order is not None
    assert order.state == "granted"
    assert len(payments) == 1
    assert len(grants) == 1
    assert len(audits) == 2
    assert len(entries) == 1
    assert entries[0].entry_type == "top_up_grant"
    assert entries[0].units == 2_000
    assert balance is not None
    assert balance.available_units == 2_000
    assert balance.reserved_units == 0
    assert balance.committed_units == 0
    assert balance.version == 1


class _AlwaysFailBalanceRepository:
    def __init__(self, wrapped) -> None:
        self._wrapped = wrapped

    async def get_snapshot(self, **kwargs):
        return await self._wrapped.get_snapshot(**kwargs)

    async def compare_and_swap(self, request):
        return BalanceCompareAndSwapResult(
            updated=False,
            previous_version=request.expected_version,
            resulting_version=request.expected_version,
        )


class _FailCasAtomicUnitOfWork(SqlAlchemyAtomicTopUpEntitlementUnitOfWork):
    async def __aenter__(self):
        unit = await super().__aenter__()
        self.balances = _AlwaysFailBalanceRepository(self.balances)
        return unit


@pytest.mark.asyncio
async def test_postgresql_bridge_cas_failure_rolls_back_every_table(
    postgresql_bridge_gate,
) -> None:
    session_factory = postgresql_bridge_gate
    await _seed_order(session_factory)
    service = _service(
        session_factory,
        uow_type=_FailCasAtomicUnitOfWork,
    )

    with pytest.raises(
        Exception,
        match="compare-and-swap conflict",
    ):
        await service.post_approved_top_up(_command())

    order, payments, grants, audits, entries, balance = await _counts_and_state(session_factory)

    assert order is not None
    assert order.state == "awaiting_payment"
    assert payments == []
    assert grants == []
    assert audits == []
    assert entries == []
    assert balance is None
