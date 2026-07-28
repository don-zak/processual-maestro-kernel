from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from processual_api.admin_marketplace.application.commands import (
    CommercialOperationContext,
    CreateOrderCommand,
)
from processual_api.admin_marketplace.application.errors import (
    AdminMarketplaceChannelPolicyError,
)
from processual_api.admin_marketplace.application.services import (
    AdminMarketplaceCommercialCoreService,
)
from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAuthorityContext,
)
from processual_api.admin_marketplace.contracts import (
    OfferStatus,
    SalesChannel,
)


def _authority_context() -> AdminMarketplaceAuthorityContext:
    return AdminMarketplaceAuthorityContext(
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        platform_authorities=frozenset({"platform_admin"}),
        active_platform_admin=True,
        recent_mfa_step_up=True,
    )


def _create_order_command() -> CreateOrderCommand:
    return CreateOrderCommand(
        context=CommercialOperationContext(
            authority=_authority_context(),
            correlation_id="correlation-order-policy",
        ),
        order_id=uuid.uuid4(),
        order_ref="order-policy-001",
        customer_ref="customer-001",
        offer_id=uuid.uuid4(),
        selected_channel=SalesChannel.MAESTRO_DIRECT,
    )


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        offer: object,
        eligibility: object | None,
    ) -> None:
        self.offers = SimpleNamespace(get_by_id=AsyncMock(return_value=offer))
        self.channel_eligibilities = SimpleNamespace(get_by_customer_ref=AsyncMock(return_value=eligibility))
        self.orders = SimpleNamespace(add=Mock())
        self.commercial_audit = SimpleNamespace(append=Mock())
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if exc is not None:
            await self.rollback()


class TestAdminMarketplaceOrderChannelPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_eligible_customer_channel_creates_order(
        self,
    ) -> None:
        command = _create_order_command()

        offer = SimpleNamespace(
            id=command.offer_id,
            status=OfferStatus.PUBLISHED.value,
        )
        eligibility = SimpleNamespace(
            customer_ref=command.customer_ref,
            maestro_direct_status="eligible",
            lemon_squeezy_status="eligible",
            admin_review_required=False,
        )
        unit = FakeUnitOfWork(
            offer=offer,
            eligibility=eligibility,
        )
        service = AdminMarketplaceCommercialCoreService(lambda: unit)

        order = await service.create_order(command)

        self.assertEqual(
            order.customer_ref,
            command.customer_ref,
        )
        self.assertEqual(
            order.selected_channel,
            SalesChannel.MAESTRO_DIRECT.value,
        )
        self.assertEqual(order.status, "submitted")

        unit.channel_eligibilities.get_by_customer_ref.assert_awaited_once_with(
            command.customer_ref,
            for_update=True,
        )
        unit.orders.add.assert_called_once_with(order)
        unit.commercial_audit.append.assert_called_once()
        unit.commit.assert_awaited_once()

    async def test_ineligible_customer_channel_is_rejected(
        self,
    ) -> None:
        command = _create_order_command()

        offer = SimpleNamespace(
            id=command.offer_id,
            status=OfferStatus.PUBLISHED.value,
        )
        eligibility = SimpleNamespace(
            customer_ref=command.customer_ref,
            maestro_direct_status="ineligible",
            lemon_squeezy_status="eligible",
            admin_review_required=False,
        )
        unit = FakeUnitOfWork(
            offer=offer,
            eligibility=eligibility,
        )
        service = AdminMarketplaceCommercialCoreService(lambda: unit)

        with self.assertRaises(AdminMarketplaceChannelPolicyError):
            await service.create_order(command)

        unit.orders.add.assert_not_called()
        unit.commercial_audit.append.assert_not_called()
        unit.commit.assert_not_awaited()
