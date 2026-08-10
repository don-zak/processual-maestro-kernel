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


def _row(
    *,
    identity: str,
    payload: str,
    with_evidence: bool = True,
) -> AdminMarketLemonSqueezyWebhookInbox:
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
        evidence_schema_version=1 if with_evidence else None,
        provider_customer_id="5001" if with_evidence else None,
        provider_order_id="6001" if with_evidence else None,
        provider_subscription_id="9001" if with_evidence else None,
        variant_id="8001" if with_evidence else None,
        provider_status="active" if with_evidence else None,
        provider_effective_at=NOW if with_evidence else None,
        received_at=NOW,
    )


async def _create_engine_with_table():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(AdminMarketLemonSqueezyWebhookInbox.__table__.create)
    return engine


@pytest.mark.asyncio
async def test_sqlite_accepts_successive_events_for_same_resource_binding() -> None:
    engine = await _create_engine_with_table()
    try:
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
    engine = await _create_engine_with_table()
    try:
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


@pytest.mark.asyncio
async def test_sqlite_accepts_legacy_row_without_invented_evidence() -> None:
    engine = await _create_engine_with_table()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add(
                _row(identity="1" * 64, payload="a" * 64, with_evidence=False)
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_rejects_partial_evidence_snapshot() -> None:
    engine = await _create_engine_with_table()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            row = _row(identity="1" * 64, payload="a" * 64, with_evidence=False)
            row.evidence_schema_version = 1
            row.provider_customer_id = "5001"
            session.add(row)
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()
