from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.contract_service import (
    DirectContractCompletionService,
)
from processual_api.admin_marketplace.errors import (
    CommercialOrderNotFoundError,
    ContractCompletionConflictError,
)

NOW = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
CONTRACT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
REFERENCE_ID = uuid.UUID("abcdef12-3456-7890-abcd-ef1234567890")
EVENT_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


class OrderRepository:
    def __init__(self, order) -> None:
        self.order = order
        self.calls = []

    async def get_by_ref(self, order_ref, *, for_update=False):
        self.calls.append((order_ref, for_update))
        return self.order if self.order and self.order.order_ref == order_ref else None


class ContractRepository:
    def __init__(self) -> None:
        self.items = []

    async def get_by_order_id(self, order_id, *, for_update=False):
        return next((item for item in self.items if item.order_id == order_id), None)

    def add(self, contract) -> None:
        self.items.append(contract)


class AuditRepository:
    def __init__(self) -> None:
        self.items = []

    def append(self, record) -> None:
        self.items.append(record)


class UnitOfWork:
    def __init__(self, order) -> None:
        self.orders = OrderRepository(order)
        self.contracts = ContractRepository()
        self.commercial_audit = AuditRepository()
        self.commit_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self) -> None:
        self.commit_calls += 1


def order(*, customer_ref="customer_001", contract_version="tn-direct-v1"):
    return SimpleNamespace(
        id=ORDER_ID,
        order_ref="ord_001",
        customer_ref=customer_ref,
        selected_channel="maestro_direct",
        status="awaiting_contract",
        contract_status="pending",
        payment_status="pending",
        payment_reference="TN-34567890",
        offer_snapshot={"contract_version": contract_version},
        payment_destination_snapshot={
            "destination_ref": "tn_bank_primary",
            "masked_identifier": "****************1234",
        },
        updated_at=NOW,
    )


def service(unit: UnitOfWork) -> DirectContractCompletionService:
    return DirectContractCompletionService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: CONTRACT_ID,
        reference_factory=lambda: REFERENCE_ID,
        event_id_factory=lambda: EVENT_ID,
    )


def kwargs(**changes):
    values = {
        "actor_user_id": "user_001",
        "actor_session_id": "session_001",
        "customer_ref": "customer_001",
        "order_ref": "ord_001",
        "contract_version": "tn-direct-v1",
        "correlation_id": "corr_001",
        "idempotency_key": "contract-idempotency-0001",
    }
    values.update(changes)
    return values


@pytest.mark.asyncio
async def test_authenticated_contract_completion_is_atomic_and_audited() -> None:
    unit = UnitOfWork(order())

    result = await service(unit).complete_authenticated_clickwrap(**kwargs())

    assert result.status == "completed"
    assert result.order_status == "awaiting_payment"
    assert result.payment_reference == "TN-34567890"
    assert result.payment_destination_snapshot["masked_identifier"] == "****************1234"
    assert unit.orders.order.contract_status == "completed"
    assert unit.commit_calls == 1
    assert len(unit.contracts.items) == 1
    assert len(unit.commercial_audit.items) == 1
    audit = unit.commercial_audit.items[0]
    assert audit.action == "contract_completed"
    assert audit.platform_authority == "identity_customer"
    assert audit.metadata_json["contract_version"] == "tn-direct-v1"


@pytest.mark.asyncio
async def test_contract_completion_is_idempotent_without_extra_commit_or_audit() -> None:
    unit = UnitOfWork(order())
    contract_service = service(unit)
    first = await contract_service.complete_authenticated_clickwrap(**kwargs())
    replay = await contract_service.complete_authenticated_clickwrap(**kwargs())

    assert replay.contract_ref == first.contract_ref
    assert replay.reason_code == "contract_completion_idempotent"
    assert unit.commit_calls == 1
    assert len(unit.commercial_audit.items) == 1


@pytest.mark.asyncio
async def test_customer_cannot_complete_another_customers_contract() -> None:
    unit = UnitOfWork(order(customer_ref="another_customer"))

    with pytest.raises(CommercialOrderNotFoundError):
        await service(unit).complete_authenticated_clickwrap(**kwargs())

    assert unit.commit_calls == 0


@pytest.mark.asyncio
async def test_contract_version_must_match_immutable_order_snapshot() -> None:
    unit = UnitOfWork(order(contract_version="tn-direct-v2"))

    with pytest.raises(ContractCompletionConflictError):
        await service(unit).complete_authenticated_clickwrap(**kwargs())

    assert unit.commit_calls == 0
