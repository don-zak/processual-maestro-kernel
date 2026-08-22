from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.commercial_offer_provider_binding import (
    AdminMarketOfferProviderBinding,
    is_verified_lemon_squeezy_binding,
)
from processual_api.admin_marketplace.models import AdminMarketOffer
from processual_api.billing.canonical_checkout_gate import (
    CanonicalCheckoutGateError,
    require_checkout_publication_ready,
)


@dataclass(frozen=True, slots=True)
class CanonicalCheckoutResolution:
    offer_id: uuid.UUID
    offer_ref: str
    plan_id: uuid.UUID
    display_name: str
    billing_period: str
    currency: str
    amount: Decimal
    provider_variant_id: str


async def resolve_canonical_checkout_in_session(
    *,
    session: AsyncSession,
    offer_ref: str,
) -> CanonicalCheckoutResolution:
    normalized_offer_ref = offer_ref.strip().lower()
    if not normalized_offer_ref:
        raise CanonicalCheckoutGateError("canonical_offer_ref_required")

    offer = await session.scalar(
        select(AdminMarketOffer).where(
            AdminMarketOffer.offer_code == normalized_offer_ref
        )
    )
    if offer is None:
        raise CanonicalCheckoutGateError("canonical_offer_not_found")

    binding = await session.scalar(
        select(AdminMarketOfferProviderBinding).where(
            AdminMarketOfferProviderBinding.offer_id == offer.id
        )
    )
    binding_verified = is_verified_lemon_squeezy_binding(
        binding,
        offer_id=offer.id,
    )

    require_checkout_publication_ready(
        offer_status=offer.status,
        sales_channel=offer.sales_channel,
        provider_binding_verified=binding_verified,
    )

    if binding is None:
        raise CanonicalCheckoutGateError("verified_provider_binding_required")

    provider_variant_id = binding.provider_variant_id.strip()
    if not provider_variant_id:
        raise CanonicalCheckoutGateError("verified_provider_binding_required")

    return CanonicalCheckoutResolution(
        offer_id=offer.id,
        offer_ref=offer.offer_code,
        plan_id=offer.plan_id,
        display_name=offer.display_name,
        billing_period=offer.billing_period,
        currency=offer.currency,
        amount=Decimal(offer.amount),
        provider_variant_id=provider_variant_id,
    )


__all__ = [
    "CanonicalCheckoutResolution",
    "resolve_canonical_checkout_in_session",
]
