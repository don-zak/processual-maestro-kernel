from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    AdminMarketLemonSqueezyBinding,
    AdminMarketLemonSqueezyCustomerBinding,
)


def _customer(
    customer_ref: str = "customer_001",
    provider_customer_id: str = "5001",
) -> AdminMarketLemonSqueezyCustomerBinding:
    return AdminMarketLemonSqueezyCustomerBinding(
        id=uuid.uuid4(),
        customer_ref=customer_ref,
        provider_customer_id=provider_customer_id,
    )


def _binding(
    *,
    customer_ref: str = "customer_001",
    provider_customer_id: str = "5001",
    order_id: uuid.UUID | None = None,
    provider_order_id: str = "6001",
    provider_subscription_id: str | None = "9001",
) -> AdminMarketLemonSqueezyBinding:
    return AdminMarketLemonSqueezyBinding(
        id=uuid.uuid4(),
        customer_ref=customer_ref,
        provider_customer_id=provider_customer_id,
        order_id=order_id or uuid.uuid4(),
        offer_id=uuid.uuid4(),
        subscription_id=None,
        provider_order_id=provider_order_id,
        provider_subscription_id=provider_subscription_id,
        variant_id="8001",
        currency="USD",
        total_amount="1000",
    )


async def _engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            AdminMarketLemonSqueezyCustomerBinding.__table__.create
        )
        await connection.run_sync(AdminMarketLemonSqueezyBinding.__table__.create)
    return engine


@pytest.mark.asyncio
async def test_provider_customer_has_single_internal_owner() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add_all(
                [
                    _customer("customer_001", "5001"),
                    _customer("customer_002", "5001"),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_internal_customer_has_single_provider_owner() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add_all(
                [
                    _customer("customer_001", "5001"),
                    _customer("customer_001", "5002"),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "duplicate_field",
    ["order_id", "provider_order_id", "provider_subscription_id"],
)
async def test_order_identifiers_are_unique(duplicate_field: str) -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        first = _binding()
        second = _binding(
            provider_order_id="6002",
            provider_subscription_id="9002",
        )
        setattr(second, duplicate_field, getattr(first, duplicate_field))
        async with factory() as session:
            session.add_all([_customer(), first, second])
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_same_customer_accepts_distinct_orders() -> None:
    engine = await _engine()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add_all(
                [
                    _customer(),
                    _binding(),
                    _binding(
                        provider_order_id="6002",
                        provider_subscription_id="9002",
                    ),
                ]
            )
            await session.commit()
    finally:
        await engine.dispose()
