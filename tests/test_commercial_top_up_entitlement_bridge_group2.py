from __future__ import annotations

import copy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_grant_posting_service import (
    EntitlementGrantPostingConflictError,
)
from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
)
from processual_api.billing.commercial_entitlement_ledger_persistence_contracts import (
    BalanceCompareAndSwapResult,
    LedgerAppendResult,
)
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)
from processual_api.billing.commercial_top_up_application_service import (
    TopUpApplicationServiceDisabledError,
)
from processual_api.billing.commercial_top_up_entitlement_bridge import (
    CommercialTopUpEntitlementBridgeService,
    PostApprovedTopUpCommand,
    TopUpEntitlementBridgePolicy,
    build_top_up_entitlement_bridge_status,
)
from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpOrder,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
ACCOUNT_ID = UUID("22222222-2222-2222-2222-222222222222")
SUBSCRIPTION_ID = UUID("33333333-3333-3333-3333-333333333333")
ORDER_ID = UUID("44444444-4444-4444-4444-444444444444")
ENTRY_ID = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime(2026, 7, 30, 14, 30, tzinfo=UTC)


class MemoryRepository:
    def __init__(self) -> None:
        self.items: list[object] = []

    def add(self, value: object) -> None:
        self.items.append(value)

    def append(self, value: object) -> None:
        self.items.append(value)


class OrderRepository:
    def __init__(self, order: CommercialTopUpOrder) -> None:
        self.order = order

    async def get_by_id(
        self,
        order_id: UUID,
        *,
        for_update: bool = False,
    ) -> CommercialTopUpOrder | None:
        del for_update
        return self.order if order_id == self.order.id else None


class PaymentRepository(MemoryRepository):
    async def get_by_provider_reference(self, provider_reference: str):
        return next(
            (item for item in self.items if item.provider_reference == provider_reference),
            None,
        )


class GrantRepository(MemoryRepository):
    async def get_for_order(
        self,
        order_id: UUID,
        *,
        for_update: bool = False,
    ):
        del for_update
        return next(
            (item for item in self.items if item.order_id == order_id),
            None,
        )


class LedgerRepository:
    def __init__(self) -> None:
        self.entries: list[EntitlementLedgerEntry] = []

    async def get_by_idempotency_key(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
        idempotency_key: str,
    ) -> EntitlementLedgerEntry | None:
        return next(
            (
                entry
                for entry in self.entries
                if entry.tenant_id == tenant_id
                and entry.subscription_id == subscription_id
                and entry.idempotency_key == idempotency_key
            ),
            None,
        )

    async def append(self, request) -> LedgerAppendResult:
        duplicate = await self.get_by_idempotency_key(
            tenant_id=request.entry.tenant_id,
            subscription_id=request.entry.subscription_id,
            idempotency_key=request.entry.idempotency_key,
        )
        if duplicate is not None:
            return LedgerAppendResult(
                entry_id=duplicate.entry_id,
                appended=False,
                duplicate=True,
                resulting_balance_version=(request.expected_balance_version),
            )

        self.entries.append(request.entry)
        return LedgerAppendResult(
            entry_id=request.entry.entry_id,
            appended=True,
            duplicate=False,
            resulting_balance_version=(request.expected_balance_version),
        )


class BalanceRepository:
    def __init__(self, *, fail_swap: bool = False) -> None:
        self.snapshot: EntitlementBalanceSnapshot | None = None
        self.version = 0
        self.fail_swap = fail_swap

    async def get_snapshot(
        self,
        *,
        tenant_id: UUID,
        subscription_id: UUID,
    ):
        if self.snapshot is None:
            return None
        if self.snapshot.tenant_id != tenant_id or self.snapshot.subscription_id != subscription_id:
            return None
        return self.snapshot, self.version

    async def compare_and_swap(
        self,
        request,
    ) -> BalanceCompareAndSwapResult:
        if self.fail_swap or request.expected_version != self.version:
            return BalanceCompareAndSwapResult(
                updated=False,
                previous_version=self.version,
                resulting_version=self.version,
            )

        previous_version = self.version
        self.version += 1
        self.snapshot = EntitlementBalanceSnapshot(
            tenant_id=request.tenant_id,
            subscription_id=request.subscription_id,
            available_units=request.available_units,
            reserved_units=request.reserved_units,
            committed_units=request.committed_units,
            calculated_at=request.calculated_at,
        )
        return BalanceCompareAndSwapResult(
            updated=True,
            previous_version=previous_version,
            resulting_version=self.version,
        )


class FakeAtomicUnitOfWork:
    def __init__(self, *, fail_cas: bool = False) -> None:
        self.orders = OrderRepository(_order())
        self.payments = PaymentRepository()
        self.grants = GrantRepository()
        self.audit = MemoryRepository()
        self.ledger = LedgerRepository()
        self.balances = BalanceRepository(fail_swap=fail_cas)
        self.commits = 0
        self.rollbacks = 0
        self._snapshot = None

    async def __aenter__(self):
        self._snapshot = {
            "order_state": self.orders.order.state,
            "payments": copy.copy(self.payments.items),
            "grants": copy.copy(self.grants.items),
            "audit": copy.copy(self.audit.items),
            "entries": copy.copy(self.ledger.entries),
            "balance": self.balances.snapshot,
            "version": self.balances.version,
        }
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        del exc
        del traceback
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.commits += 1
        self._snapshot = None

    async def rollback(self) -> None:
        self.rollbacks += 1
        if self._snapshot is None:
            return
        self.orders.order.state = self._snapshot["order_state"]
        self.payments.items[:] = self._snapshot["payments"]
        self.grants.items[:] = self._snapshot["grants"]
        self.audit.items[:] = self._snapshot["audit"]
        self.ledger.entries[:] = self._snapshot["entries"]
        self.balances.snapshot = self._snapshot["balance"]
        self.balances.version = self._snapshot["version"]
        self._snapshot = None


def _order() -> CommercialTopUpOrder:
    return CommercialTopUpOrder(
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
        idempotency_key="order-idempotency-1",
        state="awaiting_payment",
    )


def _command(
    *,
    verified_amount: Decimal = Decimal("118.00"),
) -> PostApprovedTopUpCommand:
    return PostApprovedTopUpCommand(
        tenant_id=TENANT_ID,
        order_id=ORDER_ID,
        provider_reference="provider-payment-1",
        verified_amount=verified_amount,
        verified_currency="USD",
        immutable_evidence_reference="evidence://payment/1",
        settlement_reference="settlement://payment/1",
        actor_reference="payment-verifier:test",
        occurred_at=NOW,
    )


def _enabled_policy() -> TopUpEntitlementBridgePolicy:
    return TopUpEntitlementBridgePolicy(
        enabled=True,
        writes_enabled=True,
    )


@pytest.mark.asyncio
async def test_bridge_is_fail_closed_by_default() -> None:
    uow = FakeAtomicUnitOfWork()
    service = CommercialTopUpEntitlementBridgeService(
        unit_of_work_factory=lambda: uow,
    )

    with pytest.raises(
        TopUpApplicationServiceDisabledError,
        match="bridge is disabled",
    ):
        await service.post_approved_top_up(_command())

    assert uow.commits == 0
    assert uow.rollbacks == 0


@pytest.mark.asyncio
async def test_approved_top_up_posts_all_records_atomically() -> None:
    uow = FakeAtomicUnitOfWork()
    service = CommercialTopUpEntitlementBridgeService(
        unit_of_work_factory=lambda: uow,
        policy=_enabled_policy(),
        entry_id_factory=lambda: ENTRY_ID,
    )

    result = await service.post_approved_top_up(_command())

    assert result.committed is True
    assert result.duplicate is False
    assert result.ledger_entry_id == ENTRY_ID
    assert result.available_units == 2_000
    assert result.resulting_balance_version == 1
    assert uow.orders.order.state == "granted"
    assert len(uow.payments.items) == 1
    assert len(uow.grants.items) == 1
    assert len(uow.audit.items) == 2
    assert len(uow.ledger.entries) == 1
    assert uow.commits == 1
    assert uow.rollbacks == 0


@pytest.mark.asyncio
async def test_provider_replay_is_idempotent() -> None:
    uow = FakeAtomicUnitOfWork()
    service = CommercialTopUpEntitlementBridgeService(
        unit_of_work_factory=lambda: uow,
        policy=_enabled_policy(),
        entry_id_factory=lambda: ENTRY_ID,
    )

    first = await service.post_approved_top_up(_command())
    replay = await service.post_approved_top_up(_command())

    assert first.committed is True
    assert replay.committed is False
    assert replay.duplicate is True
    assert replay.ledger_entry_id == ENTRY_ID
    assert len(uow.payments.items) == 1
    assert len(uow.grants.items) == 1
    assert len(uow.audit.items) == 2
    assert len(uow.ledger.entries) == 1
    assert uow.commits == 2


@pytest.mark.asyncio
async def test_amount_mismatch_rolls_back_without_records() -> None:
    uow = FakeAtomicUnitOfWork()
    service = CommercialTopUpEntitlementBridgeService(
        unit_of_work_factory=lambda: uow,
        policy=_enabled_policy(),
    )

    with pytest.raises(
        Exception,
        match="verified amount does not match",
    ):
        await service.post_approved_top_up(_command(verified_amount=Decimal("117.99")))

    assert len(uow.payments.items) == 0
    assert len(uow.grants.items) == 0
    assert len(uow.audit.items) == 0
    assert len(uow.ledger.entries) == 0
    assert uow.orders.order.state == "awaiting_payment"
    assert uow.rollbacks >= 1


@pytest.mark.asyncio
async def test_cas_conflict_rolls_back_before_commercial_records() -> None:
    uow = FakeAtomicUnitOfWork(fail_cas=True)
    service = CommercialTopUpEntitlementBridgeService(
        unit_of_work_factory=lambda: uow,
        policy=_enabled_policy(),
    )

    with pytest.raises(
        EntitlementGrantPostingConflictError,
        match="compare-and-swap",
    ):
        await service.post_approved_top_up(_command())

    assert len(uow.payments.items) == 0
    assert len(uow.grants.items) == 0
    assert len(uow.audit.items) == 0
    assert len(uow.ledger.entries) == 0
    assert uow.balances.snapshot is None
    assert uow.balances.version == 0
    assert uow.orders.order.state == "awaiting_payment"
    assert uow.commits == 0
    assert uow.rollbacks >= 1


def test_bridge_status_remains_disabled() -> None:
    status = build_top_up_entitlement_bridge_status()

    assert status["status"] == "draft_review"
    assert status["single_database_transaction_required"] is True
    assert status["payment_grant_audit_ledger_atomic"] is True
    assert status["fail_closed_by_default"] is True
    assert status["enabled"] is False
    assert status["writes_enabled"] is False
    assert status["runtime_wiring_enabled"] is False
    assert status["commercial_activation_enabled"] is False
