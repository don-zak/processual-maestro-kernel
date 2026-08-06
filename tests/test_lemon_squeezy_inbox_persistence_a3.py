from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.lemon_squeezy_persistence import (
    AdminMarketLemonSqueezyWebhookInbox,
)

NOW = datetime(2026, 8, 6, 10, 0, tzinfo=UTC)


def _row(*, identity: str, payload: str) -> AdminMarketLemonSqueezyWebhookInbox:
    return AdminMarketLemonSqueezyWebhookInbox(
        id=uuid.uuid4(),
        event_identity_hash=identity,
        payload_digest=payload,
        event_name="subscription_updated",
        resource_type="subscriptions",
        external_resource_id="9001",
        store_id="7001",
        customer_ref="customer_001",
        order_ref="order_001",
        offer_ref="starter_monthly",
        test_mode=False,
        processing_status="received",
        attempt_count=0,
        received_at=NOW,
    )


@pytest.mark.asyncio
async def test_sqlite_accepts_successive_events_for_same_resource_binding() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                AdminMarketLemonSqueezyWebhookInbox.__table__.create
            )

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    _row(identity="1" * 64, payload="a" * 64),
                    _row(identity="2" * 64, payload="b" * 64),
                ]
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_still_rejects_duplicate_payload_digest() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                AdminMarketLemonSqueezyWebhookInbox.__table__.create
            )

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    _row(identity="1" * 64, payload="a" * 64),
                    _row(identity="2" * 64, payload="a" * 64),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()
