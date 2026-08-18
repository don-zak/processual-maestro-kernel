from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.commercial_catalog_materialization import (
    materialize_canonical_commercial_catalog_in_session,
)
from processual_api.admin_marketplace.commercial_offer_projection import (
    build_lemon_squeezy_draft_offer_projections,
)
from processual_api.admin_marketplace.commercial_offer_provenance_persistence import (
    AdminMarketOfferProvenance,
)
from processual_api.admin_marketplace.commercial_offer_provider_binding import (
    AdminMarketOfferProviderBinding,
)
from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
)
from processual_api.admin_marketplace.models import AdminMarketOffer, AdminMarketPlan
from processual_api.db.base import Base

NOW = datetime(2026, 8, 17, 16, 0, tzinfo=UTC)


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_empty_market_materializes_canonical_plans_offers_and_provenance() -> None:
    engine, factory = await _session_factory()
    expected_plan_count = len(build_commercial_plan_projections())
    expected_offer_count = len(build_lemon_squeezy_draft_offer_projections())

    try:
        async with factory() as session:
            result = await materialize_canonical_commercial_catalog_in_session(
                session=session,
                generated_at=NOW,
            )
            await session.commit()

            plan_count = await session.scalar(
                select(func.count()).select_from(AdminMarketPlan)
            )
            offer_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOffer)
            )
            provenance_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOfferProvenance)
            )
            provider_binding_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOfferProviderBinding)
            )

        assert len(result.plans.created) == expected_plan_count
        assert len(result.offers) == expected_offer_count
        assert all(item.created for item in result.offers)
        assert all(item.provenance_verified for item in result.offers)
        assert plan_count == expected_plan_count
        assert offer_count == expected_offer_count
        assert provenance_count == expected_offer_count
        assert provider_binding_count == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_catalog_materialization_is_idempotent_without_provider_binding() -> None:
    engine, factory = await _session_factory()
    expected_plan_count = len(build_commercial_plan_projections())
    expected_offer_count = len(build_lemon_squeezy_draft_offer_projections())

    try:
        async with factory() as session:
            first = await materialize_canonical_commercial_catalog_in_session(
                session=session,
                generated_at=NOW,
            )
            await session.commit()
            second = await materialize_canonical_commercial_catalog_in_session(
                session=session,
                generated_at=NOW,
            )
            await session.commit()

            plan_count = await session.scalar(
                select(func.count()).select_from(AdminMarketPlan)
            )
            offer_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOffer)
            )
            provenance_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOfferProvenance)
            )
            provider_binding_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOfferProviderBinding)
            )

        assert first.plans.created
        assert all(item.created for item in first.offers)
        assert second.plans.created == ()
        assert second.plans.updated == ()
        assert len(second.plans.unchanged) == expected_plan_count
        assert all(not item.created for item in second.offers)
        assert all(item.provenance_verified for item in second.offers)
        assert plan_count == expected_plan_count
        assert offer_count == expected_offer_count
        assert provenance_count == expected_offer_count
        assert provider_binding_count == 0
    finally:
        await engine.dispose()
