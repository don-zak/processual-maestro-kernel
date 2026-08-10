from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.direct_order_service import (
    TunisiaDirectOrderService,
)
from processual_api.admin_marketplace.errors import (
    DirectCommerceConflictError,
    DirectCommerceUnavailableError,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
OFFER_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
PLAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")
REFERENCE_ID = uuid.UUID("abcdef12-3456-7890-abcd-ef1234567890")
EVENT_ID = uuid.UUID("40000000-0000-0000-0000-000000000001")


class EligibilityRepository:
    def __init__(self, item) -> None:
        self.item = item
        self.calls: list[tuple[str, bool]] = []

    async def get_by_customer_ref(self, customer_ref: str, *, for_update=False):
        self.calls.append((customer_ref, for_update))
        return self.item


class OfferRepository:
    def __init__(self, item) -> None:
        self.item = item
        self.calls: list[tuple[str, str, bool]] = []

    async def get_published_direct_for_plan_code(
        self, *, plan_code: str, billing_period: str, now, for_update=False
    ):
        assert now == NOW
        self.calls.append((plan_code, billing_period, for_update))
        return self.item


class DestinationRepository:
    def __init__(self, item) -> None:
        self.item = item
        self.calls: list[bool] = []

    async def get_active_default(self, *, for_update=False):
        self.calls.append(for_update)
        return self.item


class OrderRepository:
    def __init__(self) -> None:
        self.items = []

    async def get_by_creation_idempotency_key_hash(self, key_hash, *, for_update=False):
        assert for_update is True
        return next(
            (item for item in self.items if item.creation_idempotency_key_hash == key_hash),
            None,
        )

    def add(self, item) -> None:
        self.items.append(item)


class AuditRepository:
    def __init__(self) -> None:
        self.items = []

    def append(self, item) -> None:
        self.items.append(item)


class UnitOfWork:
    def __init__(self, eligibility, offer, destination) -> None:
        self.channel_eligibilities = EligibilityRepository(eligibility)
        self.offers = OfferRepository(offer)
        self.payment_destinations = DestinationRepository(destination)
        self.orders = OrderRepository()
        self.commercial_audit = AuditRepository()
        self.commit_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self) -> None:
        self.commit_calls += 1


def eligibility(*, address_status="confirmed", country_code="TN"):
    return SimpleNamespace(
        address_status=address_status,
        country_code=country_code,
        maestro_direct_status="eligible",
        admin_review_required=False,
    )


def offer():
    return SimpleNamespace(
        id=OFFER_ID,
        plan_id=PLAN_ID,
        offer_code="starter_tn_monthly",
        display_name="Starter Tunisia Monthly",
        amount=Decimal("49.900"),
    )


def destination():
    return SimpleNamespace(
        destination_ref="tn_bank_primary",
        display_name="Primary Tunisia Bank",
        destination_type="bank_account",
        institution_name="Tunisia Bank",
        account_holder_name="Processual Maestro",
        masked_identifier="****************1234",
        encrypted_identifier="ciphertext-must-never-leave-storage",
        instructions="Use the order payment reference.",
    )


def service(unit: UnitOfWork) -> TunisiaDirectOrderService:
    return TunisiaDirectOrderService(
        unit_of_work_factory=lambda: unit,
        clock=lambda: NOW,
        id_factory=lambda: ORDER_ID,
        reference_factory=lambda: REFERENCE_ID,
        event_id_factory=lambda: EVENT_ID,
    )


@pytest.mark.asyncio
async def test_payment_option_requires_confirmed_tunisian_address() -> None:
    unit = UnitOfWork(eligibility(address_status="unverified"), offer(), destination())

    result = await service(unit).evaluate_payment_option(
        customer_ref="customer_001", plan_ref="starter", billing_period="monthly"
    )

    assert result.visible is False
    assert result.reason_code == "confirmed_customer_address_required"
    assert unit.offers.calls == []
    assert unit.payment_destinations.calls == []


@pytest.mark.asyncio
async def test_payment_option_is_visible_only_when_every_gate_is_satisfied() -> None:
    unit = UnitOfWork(eligibility(), offer(), destination())

    result = await service(unit).evaluate_payment_option(
        customer_ref="customer_001", plan_ref="starter", billing_period="monthly"
    )

    assert result.visible is True
    assert result.address_status == "confirmed"
    assert result.country_code == "TN"
    assert result.sales_channel == "maestro_direct"
    assert result.currency == "TND"
    assert result.amount == Decimal("49.900")


@pytest.mark.asyncio
async def test_order_is_atomic_idempotent_and_contains_only_safe_destination_data() -> None:
    unit = UnitOfWork(eligibility(), offer(), destination())
    direct_service = service(unit)
    kwargs = {
        "actor_user_id": "user_001",
        "actor_session_id": "session_001",
        "customer_ref": "customer_001",
        "plan_ref": "starter",
        "billing_period": "monthly",
        "correlation_id": "corr_001",
        "idempotency_key": "idempotency-key-0001",
    }

    created = await direct_service.create_order(**kwargs)
    replayed = await direct_service.create_order(**kwargs)

    assert created.order_ref == replayed.order_ref
    assert replayed.reason_code == "commercial_order_create_idempotent"
    assert unit.commit_calls == 1
    assert len(unit.orders.items) == 1
    assert len(unit.commercial_audit.items) == 1
    assert unit.commercial_audit.items[0].platform_authority == "identity_customer"
    assert unit.commercial_audit.items[0].action == "order_created"
    snapshot = created.payment_destination_snapshot
    assert snapshot["masked_identifier"] == "****************1234"
    assert "encrypted_identifier" not in snapshot
    assert "raw_account_identifier" not in snapshot
    assert "ciphertext" not in str(snapshot).lower()


@pytest.mark.asyncio
async def test_idempotency_key_cannot_be_reused_for_another_plan() -> None:
    unit = UnitOfWork(eligibility(), offer(), destination())
    direct_service = service(unit)
    common = {
        "actor_user_id": "user_001",
        "actor_session_id": "session_001",
        "customer_ref": "customer_001",
        "billing_period": "monthly",
        "correlation_id": "corr_001",
        "idempotency_key": "idempotency-key-0001",
    }
    await direct_service.create_order(plan_ref="starter", **common)

    with pytest.raises(DirectCommerceConflictError):
        await direct_service.create_order(plan_ref="business", **common)


@pytest.mark.asyncio
async def test_order_creation_rechecks_default_destination_under_lock() -> None:
    unit = UnitOfWork(eligibility(), offer(), None)

    with pytest.raises(
        DirectCommerceUnavailableError,
        match="Direct commerce is unavailable",
    ) as error:
        await service(unit).create_order(
            actor_user_id="user_001",
            actor_session_id="session_001",
            customer_ref="customer_001",
            plan_ref="starter",
            billing_period="monthly",
            correlation_id="corr_001",
            idempotency_key="idempotency-key-0001",
        )

    assert error.value.reason_code == "active_default_payment_destination_required"
    assert unit.payment_destinations.calls == [True]
    assert unit.commit_calls == 0
