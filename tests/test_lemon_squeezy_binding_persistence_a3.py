from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    AdminMarketLemonSqueezyBinding,
    AdminMarketLemonSqueezyCustomer,
)

NOW = datetime(2026, 8, 6, 12, 30, tzinfo=UTC)


def _customer(
    *,
    customer_ref: str = "customer_001",
    provider_customer_id: str = "5001",
) -> AdminMarketLemonSqueezyCustomer:
    return AdminMarketLemonSqueezyCustomer(
        id=uuid.uuid4(),
        customer_ref=customer_ref,
        provider_customer_id=provider_customer_id,
    )


def _binding(
    *,
    customer_binding_id: uuid.UUID,
    order_id: uuid.UUID | None = None,
    provider_order_id: str = "6001",
    provider_subscription_id: str | None = "9001",
) -> AdminMarketLemonSqueezyBinding:
    return AdminMarketLemonSqueezyBinding(
        id=uuid.uuid4(),
        customer_binding_id=customer_binding_id,
        order_id=order_id or uuid.uuid4(),
        offer_id=uuid.uuid4(),
        subscription_id=uuid.uuid4(),
        provider_order_id=provider_order_id,
        provider_subscription_id=provider_subscription_id,
        variant_id="8001",
        currency="USD",
        total_amount="1000",
        last_provider_effective_at=NOW,
    )


async def _create_engine_with_tables():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(AdminMarketLemonSqueezyCustomer.__table__.create)
        await connection.run_sync(AdminMarketLemonSqueezyBinding.__table__.create)
    return engine


@pytest.mark.asyncio
async def test_provider_customer_cannot_belong_to_two_internal_customers() -> None:
    engine = await _create_engine_with_tables()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    _customer(customer_ref="customer_001", provider_customer_id="5001"),
                    _customer(customer_ref="customer_002", provider_customer_id="5001"),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_internal_customer_cannot_bind_multiple_provider_customers() -> None:
    engine = await _create_engine_with_tables()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            session.add_all(
                [
                    _customer(customer_ref="customer_001", provider_customer_id="5001"),
                    _customer(customer_ref="customer_001", provider_customer_id="5002"),
                ]
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("order_id", uuid.UUID("00000000-0000-0000-0000-000000000123")),
        ("provider_order_id", "6001"),
        ("provider_subscription_id", "9001"),
    ],
)
async def test_order_and_provider_identifiers_are_globally_unique(
    override: str,
    value: object,
) -> None:
    engine = await _create_engine_with_tables()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        customer = _customer()
        first = _binding(customer_binding_id=customer.id)
        second_kwargs: dict[str, object] = {
            "customer_binding_id": customer.id,
            "provider_order_id": "6002",
            "provider_subscription_id": "9002",
        }
        setattr(first, override, value)
        second_kwargs[override] = value
        second = _binding(**second_kwargs)

        async with session_factory() as session:
            session.add_all([customer, first, second])
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_same_customer_can_have_successive_distinct_orders() -> None:
    engine = await _create_engine_with_tables()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        customer = _customer()
        async with session_factory() as session:
            session.add_all(
                [
                    customer,
                    _binding(
                        customer_binding_id=customer.id,
                        provider_order_id="6001",
                        provider_subscription_id="9001",
                    ),
                    _binding(
                        customer_binding_id=customer.id,
                        provider_order_id="6002",
                        provider_subscription_id="9002",
                    ),
                ]
            )
            await session.commit()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_null_provider_subscription_allows_pre_subscription_orders() -> None:
    engine = await _create_engine_with_tables()
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        customer = _customer()
        async with session_factory() as session:
            session.add_all(
                [
                    customer,
                    _binding(
                        customer_binding_id=customer.id,
                        provider_order_id="6001",
                        provider_subscription_id=None,
                    ),
                    _binding(
                        customer_binding_id=customer.id,
                        provider_order_id="6002",
                        provider_subscription_id=None,
                    ),
                ]
            )
            await session.commit()
    finally:
        await engine.dispose()
