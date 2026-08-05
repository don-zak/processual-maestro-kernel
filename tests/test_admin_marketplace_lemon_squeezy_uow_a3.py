from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from processual_api.admin_marketplace.lemon_squeezy_persistence import (
    SqlAlchemyLemonSqueezyWebhookInboxRepository,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)


@pytest.mark.asyncio
async def test_uow_exposes_webhook_inbox_on_the_same_session() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    uow = SqlAlchemyAdminMarketplaceUnitOfWork(lambda: session)

    async with uow as active:
        assert isinstance(
            active.lemon_squeezy_webhook_inbox,
            SqlAlchemyLemonSqueezyWebhookInboxRepository,
        )
        assert active.lemon_squeezy_webhook_inbox._session is session
        await active.commit()

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_uow_rolls_back_uncommitted_webhook_work() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    uow = SqlAlchemyAdminMarketplaceUnitOfWork(lambda: session)

    async with uow as active:
        assert active.lemon_squeezy_webhook_inbox._session is session

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_uow_rolls_back_webhook_work_on_exception() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    uow = SqlAlchemyAdminMarketplaceUnitOfWork(lambda: session)

    with pytest.raises(RuntimeError, match="boom"):
        async with uow as active:
            assert active.lemon_squeezy_webhook_inbox._session is session
            raise RuntimeError("boom")

    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


def test_uow_webhook_repository_has_no_activation_surface() -> None:
    repository = SqlAlchemyLemonSqueezyWebhookInboxRepository(MagicMock())

    forbidden = {
        "activate_subscription",
        "activate_entitlements",
        "reconcile_payment",
        "verify_and_activate",
        "process_event",
    }

    assert forbidden.isdisjoint(set(dir(repository)))
