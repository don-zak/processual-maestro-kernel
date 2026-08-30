from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.commercial_offer_projection import (
    CommercialOfferProjection,
)
from processual_api.admin_marketplace.commercial_offer_provenance import (
    build_offer_provenance,
)
from processual_api.admin_marketplace.commercial_offer_provenance_persistence import (
    AdminMarketOfferProvenance,
)
from processual_api.admin_marketplace.commercial_offer_provenance_verifier import (
    verify_commercial_offer_provenance,
)
from processual_api.admin_marketplace.models import AdminMarketOffer, AdminMarketPlan


@dataclass(frozen=True, slots=True)
class CommercialOfferMaterializationResult:
    offer_id: uuid.UUID
    offer_code: str
    created: bool
    provenance_verified: bool


def _require_canonical_plan(plan: AdminMarketPlan | None, expected_code: str) -> AdminMarketPlan:
    if plan is None:
        raise ValueError("canonical commercial plan must be materialized first")
    if plan.plan_code.strip().lower() != expected_code:
        raise ValueError("materialized plan identity conflicts with offer projection")
    metadata = dict(plan.metadata_json or {})
    if metadata.get("lifecycle_state") != "canonical":
        raise ValueError("legacy or isolated plan cannot receive canonical offers")
    if metadata.get("commercial_authority") == "compatibility_only":
        raise ValueError("compatibility-only plan cannot receive canonical offers")
    return plan


def _offer_matches_projection(
    offer: AdminMarketOffer,
    projection: CommercialOfferProjection,
    plan: AdminMarketPlan,
) -> bool:
    return (
        offer.offer_code == projection.offer_code
        and offer.plan_id == plan.id
        and offer.display_name == projection.display_name
        and offer.sales_channel == projection.sales_channel
        and offer.billing_period == projection.billing_period
        and offer.currency == projection.currency
        and offer.amount == projection.amount
        and bool(offer.customer_specific) == projection.customer_specific
    )


async def materialize_commercial_offer_in_session(
    *,
    session: AsyncSession,
    projection: CommercialOfferProjection,
    generated_at: datetime,
) -> CommercialOfferMaterializationResult:
    """Materialize one immutable draft offer and its provenance atomically.

    The caller owns commit/rollback. Existing non-draft offers are never revised by
    this function; a changed price or FX quote must produce a new versioned offer.
    """

    if generated_at.tzinfo is None:
        raise ValueError("commercial offer materialization clock must be timezone-aware")

    plan = await session.scalar(
        select(AdminMarketPlan).where(AdminMarketPlan.plan_code == projection.plan_code)
    )
    plan = _require_canonical_plan(plan, projection.plan_code)

    existing = await session.scalar(
        select(AdminMarketOffer).where(AdminMarketOffer.offer_code == projection.offer_code)
    )
    if existing is not None:
        if not _offer_matches_projection(existing, projection, plan):
            raise ValueError("existing offer conflicts with immutable canonical projection")
        provenance_row = await session.scalar(
            select(AdminMarketOfferProvenance).where(
                AdminMarketOfferProvenance.offer_id == existing.id
            )
        )
        if provenance_row is None:
            raise ValueError("existing canonical offer is missing immutable provenance")
        verification = verify_commercial_offer_provenance(
            offer=existing,
            plan=plan,
            persisted=provenance_row,
        )
        if not verification.verified:
            raise ValueError(
                f"existing canonical offer provenance failed: {verification.reason_code}"
            )
        return CommercialOfferMaterializationResult(
            offer_id=existing.id,
            offer_code=existing.offer_code,
            created=False,
            provenance_verified=True,
        )

    offer_id = uuid.uuid4()
    offer = AdminMarketOffer(
        id=offer_id,
        offer_code=projection.offer_code,
        plan_id=plan.id,
        display_name=projection.display_name,
        currency=projection.currency,
        sales_channel=projection.sales_channel,
        billing_period=projection.billing_period,
        amount=projection.amount,
        status="draft",
        effective_at=projection.effective_at,
        expires_at=projection.expires_at,
        customer_specific=projection.customer_specific,
        created_at=generated_at,
        updated_at=generated_at,
    )
    provenance = build_offer_provenance(
        projection=projection,
        generated_at=generated_at,
    )
    provenance_row = AdminMarketOfferProvenance(
        id=uuid.uuid4(),
        offer_id=offer_id,
        provenance_version=provenance.provenance_version,
        source_pricing_version=provenance.source_pricing_version,
        source_pricebook_version=provenance.source_pricebook_version,
        evidence_json=provenance.payload(),
        evidence_sha256=provenance.digest_sha256(),
        created_at=generated_at,
    )
    session.add(offer)
    session.add(provenance_row)

    return CommercialOfferMaterializationResult(
        offer_id=offer_id,
        offer_code=projection.offer_code,
        created=True,
        provenance_verified=True,
    )


__all__ = [
    "CommercialOfferMaterializationResult",
    "materialize_commercial_offer_in_session",
]
