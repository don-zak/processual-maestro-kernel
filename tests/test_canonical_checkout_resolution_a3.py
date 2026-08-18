from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.commercial_catalog_materialization import (
    materialize_canonical_commercial_catalog_in_session,
)
from processual_api.admin_marketplace.commercial_offer_provider_binding import (
    AdminMarketOfferProviderBinding,
)
from processual_api.admin_marketplace.models import AdminMarketOffer, AdminMarketPlan
from processual_api.billing.canonical_checkout_gate import CanonicalCheckoutGateError
from processual_api.billing.canonical_checkout_resolution import (
    resolve_canonical_checkout_in_session,
)
from processual_api.db.base import Base

NOW = datetime(2026, 8, 17, 17, 0, tzinfo=UTC)


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_offer(
    session,
    *,
    status: str = "draft",
    sales_channel: str = "lemon_squeezy",
) -> AdminMarketOffer:
    plan = AdminMarketPlan(
        id=uuid.uuid4(),
        plan_code="starter",
        display_name="Starter",
        entitlement_profile_ref="starter",
        quota_profile_ref="starter",
        metadata_json={"lifecycle_state": "canonical"},
        created_at=NOW,
        updated_at=NOW,
    )
    offer = AdminMarketOffer(
        id=uuid.uuid4(),
        offer_code="starter-monthly",
        plan_id=plan.id,
        display_name="Starter Monthly",
        currency="USD" if sales_channel == "lemon_squeezy" else "TND",
        sales_channel=sales_channel,
        billing_period="monthly",
        amount=Decimal("49.000"),
        status=status,
        customer_specific=False,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(plan)
    session.add(offer)
    await session.flush()
    return offer


@pytest.mark.asyncio
async def test_checkout_resolution_rejects_unknown_offer() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            with pytest.raises(CanonicalCheckoutGateError) as captured:
                await resolve_canonical_checkout_in_session(
                    session=session,
                    offer_ref="missing-offer",
                )
        assert captured.value.reason_code == "canonical_offer_not_found"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_checkout_resolution_blocks_draft_offer_without_binding() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_offer(session, status="draft")
            with pytest.raises(CanonicalCheckoutGateError) as captured:
                await resolve_canonical_checkout_in_session(
                    session=session,
                    offer_ref="starter-monthly",
                )
        assert captured.value.reason_code == "published_offer_required"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_materialized_canonical_catalog_stays_checkout_closed() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            materialized = await materialize_canonical_commercial_catalog_in_session(
                session=session,
                generated_at=NOW,
            )
            await session.commit()

            assert materialized.offers
            offer_ref = materialized.offers[0].offer_code
            with pytest.raises(CanonicalCheckoutGateError) as captured:
                await resolve_canonical_checkout_in_session(
                    session=session,
                    offer_ref=offer_ref,
                )

        assert captured.value.reason_code == "published_offer_required"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_checkout_resolution_requires_lemon_squeezy_channel() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_offer(
                session,
                status="published",
                sales_channel="maestro_direct",
            )
            with pytest.raises(CanonicalCheckoutGateError) as captured:
                await resolve_canonical_checkout_in_session(
                    session=session,
                    offer_ref="starter-monthly",
                )
        assert captured.value.reason_code == "lemon_squeezy_offer_required"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_checkout_resolution_requires_provider_binding() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            await _seed_offer(session, status="published")
            with pytest.raises(CanonicalCheckoutGateError) as captured:
                await resolve_canonical_checkout_in_session(
                    session=session,
                    offer_ref="starter-monthly",
                )
        assert captured.value.reason_code == "verified_provider_binding_required"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("binding_status", ("pending", "revoked"))
async def test_checkout_resolution_requires_verified_provider_binding(
    binding_status: str,
) -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            offer = await _seed_offer(session, status="published")
            verified = binding_status == "revoked"
            session.add(
                AdminMarketOfferProviderBinding(
                    id=uuid.uuid4(),
                    offer_id=offer.id,
                    provider="lemon_squeezy",
                    provider_variant_id="12345",
                    status=binding_status,
                    verification_reference=(
                        "ls-variant-12345" if verified else None
                    ),
                    verified_at=NOW if verified else None,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await session.flush()
            with pytest.raises(CanonicalCheckoutGateError) as captured:
                await resolve_canonical_checkout_in_session(
                    session=session,
                    offer_ref="starter-monthly",
                )
        assert captured.value.reason_code == "verified_provider_binding_required"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_checkout_resolution_returns_variant_from_verified_binding() -> None:
    engine, factory = await _session_factory()
    try:
        async with factory() as session:
            offer = await _seed_offer(session, status="published")
            session.add(
                AdminMarketOfferProviderBinding(
                    id=uuid.uuid4(),
                    offer_id=offer.id,
                    provider="lemon_squeezy",
                    provider_variant_id="12345",
                    status="verified",
                    verification_reference="ls-variant-12345",
                    verified_at=NOW,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            await session.flush()
            resolution = await resolve_canonical_checkout_in_session(
                session=session,
                offer_ref="Starter-Monthly",
            )

        assert resolution.offer_ref == "starter-monthly"
        assert resolution.provider_variant_id == "12345"
    finally:
        await engine.dispose()
