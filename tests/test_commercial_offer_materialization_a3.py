from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.commercial_offer_materialization import (
    materialize_commercial_offer_in_session,
)
from processual_api.admin_marketplace.commercial_offer_projection import (
    build_lemon_squeezy_draft_offer_projections,
)
from processual_api.admin_marketplace.commercial_offer_provenance_persistence import (
    AdminMarketOfferProvenance,
)
from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
)
from processual_api.admin_marketplace.models import AdminMarketOffer, AdminMarketPlan
from processual_api.db.base import Base

NOW = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _plan_row(plan_code: str) -> AdminMarketPlan:
    projection = next(
        item for item in build_commercial_plan_projections() if item.plan_code == plan_code
    )
    return AdminMarketPlan(
        plan_code=projection.plan_code,
        display_name=projection.display_name,
        entitlement_profile_ref=projection.entitlement_profile_ref,
        quota_profile_ref=projection.quota_profile_ref,
        metadata_json={**projection.metadata, "lifecycle_state": "canonical"},
    )


@pytest.mark.asyncio
async def test_offer_and_provenance_materialize_together_idempotently() -> None:
    engine, factory = await _session_factory()
    projection = build_lemon_squeezy_draft_offer_projections()[0]

    try:
        async with factory() as session:
            session.add(_plan_row(projection.plan_code))
            await session.commit()

            created = await materialize_commercial_offer_in_session(
                session=session,
                projection=projection,
                generated_at=NOW,
            )
            await session.commit()
            replayed = await materialize_commercial_offer_in_session(
                session=session,
                projection=projection,
                generated_at=NOW,
            )

            offer_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOffer)
            )
            provenance_count = await session.scalar(
                select(func.count()).select_from(AdminMarketOfferProvenance)
            )

        assert created.created is True
        assert replayed.created is False
        assert replayed.offer_id == created.offer_id
        assert replayed.provenance_verified is True
        assert offer_count == 1
        assert provenance_count == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_offer_materialization_rejects_noncanonical_plan_row() -> None:
    engine, factory = await _session_factory()
    projection = build_lemon_squeezy_draft_offer_projections()[0]
    plan = _plan_row(projection.plan_code)
    plan.metadata_json = {
        **dict(plan.metadata_json),
        "lifecycle_state": "legacy_isolated",
        "commercial_authority": "compatibility_only",
    }

    try:
        async with factory() as session:
            session.add(plan)
            await session.commit()

            with pytest.raises(ValueError, match="legacy or isolated"):
                await materialize_commercial_offer_in_session(
                    session=session,
                    projection=projection,
                    generated_at=NOW,
                )
    finally:
        await engine.dispose()
