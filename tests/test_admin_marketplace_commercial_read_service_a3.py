from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.commercial_read_service import (
    AdminMarketplaceCommercialReadService,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)

NOW = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)
ORDER_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")


class Orders:
    def __init__(self, item) -> None:
        self.item = item

    async def list_recent(self, *, limit=100):
        assert limit == 100
        return (self.item,)

    async def get_by_id(self, order_id, *, for_update=False):
        assert order_id == ORDER_ID
        assert for_update is False
        return self.item


class Contracts:
    def __init__(self, item) -> None:
        self.item = item

    async def list_recent(self, *, limit=100):
        assert limit == 100
        return (self.item,)


class Unit:
    def __init__(self, order, contract) -> None:
        self.orders = Orders(order)
        self.contracts = Contracts(contract)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None


def authority(*roles: str):
    return authority_context(
        user_id="admin_001",
        session_id="session_001",
        platform_authorities=roles,
        active_platform_admin=True,
        recent_mfa_step_up=False,
    )


def records():
    order = SimpleNamespace(
        id=ORDER_ID,
        order_ref="ord_001",
        customer_ref="customer_001",
        offer_snapshot={"plan_ref": "starter", "offer_ref": "starter_tn_monthly"},
        billing_period="monthly",
        status="awaiting_payment",
        contract_status="completed",
        payment_status="pending",
        payment_reference="TN-34567890",
        total_amount=Decimal("49.900"),
        currency="TND",
        created_at=NOW,
        updated_at=NOW,
    )
    contract = SimpleNamespace(
        order_id=ORDER_ID,
        contract_ref="ctr_001",
        customer_ref="customer_001",
        contract_version="tn-direct-v1",
        status="completed",
        acceptance_method="authenticated_clickwrap",
        evidence_reference="cev_001",
        completed_at=NOW,
    )
    return order, contract


@pytest.mark.asyncio
async def test_platform_admin_reads_real_orders_and_contracts_without_mfa() -> None:
    order, contract = records()
    service = AdminMarketplaceCommercialReadService(
        unit_of_work_factory=lambda: Unit(order, contract)
    )

    orders = await service.list_orders(authority=authority("platform_admin"))
    contracts = await service.list_contracts(authority=authority("platform_admin"))

    assert orders[0].order_ref == "ord_001"
    assert orders[0].total_amount == Decimal("49.900")
    assert contracts[0].order_ref == "ord_001"
    assert contracts[0].evidence_reference == "cev_001"


@pytest.mark.asyncio
async def test_non_platform_admin_cannot_read_commercial_records() -> None:
    order, contract = records()
    service = AdminMarketplaceCommercialReadService(
        unit_of_work_factory=lambda: Unit(order, contract)
    )

    with pytest.raises(AdminMarketplaceAuthorityDeniedError):
        await service.list_orders(authority=authority("billing_admin"))
