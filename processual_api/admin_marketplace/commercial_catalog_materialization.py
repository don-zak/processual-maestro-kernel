from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.commercial_offer_materialization import (
    CommercialOfferMaterializationResult,
    materialize_commercial_offer_in_session,
)
from processual_api.admin_marketplace.commercial_offer_projection import (
    build_lemon_squeezy_draft_offer_projections,
)
from processual_api.admin_marketplace.commercial_plan_materialization import (
    CommercialPlanMaterializationResult,
    materialize_commercial_plans_in_session,
)


@dataclass(frozen=True, slots=True)
class CommercialCatalogMaterializationResult:
    plans: CommercialPlanMaterializationResult
    offers: tuple[CommercialOfferMaterializationResult, ...]


async def materialize_canonical_commercial_catalog_in_session(
    *,
    session: AsyncSession,
    generated_at: datetime,
) -> CommercialCatalogMaterializationResult:
    """Materialize canonical plans followed by Lemon draft offers atomically.

    The caller owns commit/rollback. This orchestration only creates local Admin
    Marketplace plans, draft Lemon-channel offers, and immutable provenance. It
    does not publish offers, enable checkout, or create provider-variant bindings.
    """

    if generated_at.tzinfo is None:
        raise ValueError("commercial catalog materialization clock must be timezone-aware")

    plan_result = await materialize_commercial_plans_in_session(session)

    # Offer materialization resolves plans through SQL, so make newly-added plan
    # rows visible inside the same transaction without committing any partial work.
    await session.flush()

    offer_results: list[CommercialOfferMaterializationResult] = []
    for projection in build_lemon_squeezy_draft_offer_projections():
        offer_results.append(
            await materialize_commercial_offer_in_session(
                session=session,
                projection=projection,
                generated_at=generated_at,
            )
        )

    return CommercialCatalogMaterializationResult(
        plans=plan_result,
        offers=tuple(offer_results),
    )


__all__ = [
    "CommercialCatalogMaterializationResult",
    "materialize_canonical_commercial_catalog_in_session",
]
