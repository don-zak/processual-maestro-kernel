from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)
from processual_api.admin_marketplace.router import (
    GENERIC_UNAVAILABLE,
    AdminMarketplaceRuntime,
    _commercial_read_authority,
    get_admin_marketplace_runtime,
    router,
)
from processual_api.auth.session_router import get_identity_user
from processual_api.billing.offer_pricebook import (
    OFFER_PRICEBOOK_STATUS,
    OFFER_PRICEBOOK_VERSION,
    list_offer_prices,
)


class AdminMarketplaceOfferResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offer_id: str
    plan_id: str
    plan_display_name: str
    display_name: str
    description: str
    billing_interval: str
    commercially_listed: bool
    requires_sales_contact: bool
    pricebook_version: str
    pricebook_status: str
    price_status: str
    public_price_label: str
    currency: str | None
    checkout_enabled: bool
    approval_required_before_checkout: bool
    local_payment_ready: bool
    local_payment_channel: str | None
    local_payment_currency: str | None
    local_payment_gate_reasons: tuple[str, ...]


class AdminMarketplaceOfferListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    pricebook_version: str
    pricebook_status: str
    items: tuple[AdminMarketplaceOfferResponse, ...]
    count: int


def _local_payment_gate_reasons(offer: dict[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    if offer.get("pricebook_status") != "published":
        reasons.append("offer_not_published")
    if offer.get("price_status") not in {"approved", "published"}:
        reasons.append("price_not_approved")
    if offer.get("currency") != "TND":
        reasons.append("currency_not_tnd")
    if not bool(offer.get("checkout_enabled")):
        reasons.append("checkout_disabled")
    if not bool(offer.get("commercially_listed")):
        reasons.append("offer_not_commercially_listed")
    return tuple(reasons)


def _admin_offer_payload(offer: dict[str, Any]) -> AdminMarketplaceOfferResponse:
    gate_reasons = _local_payment_gate_reasons(offer)
    local_payment_ready = not gate_reasons
    return AdminMarketplaceOfferResponse(
        offer_id=str(offer["offer_id"]),
        plan_id=str(offer["plan_id"]),
        plan_display_name=str(offer["plan_display_name"]),
        display_name=str(offer["display_name"]),
        description=str(offer["description"]),
        billing_interval=str(offer["billing_interval"]),
        commercially_listed=bool(offer["commercially_listed"]),
        requires_sales_contact=bool(offer["requires_sales_contact"]),
        pricebook_version=str(offer["pricebook_version"]),
        pricebook_status=str(offer["pricebook_status"]),
        price_status=str(offer["price_status"]),
        public_price_label=str(offer["public_price_label"]),
        currency=offer.get("currency"),
        checkout_enabled=bool(offer["checkout_enabled"]),
        approval_required_before_checkout=bool(
            offer["approval_required_before_checkout"]
        ),
        local_payment_ready=local_payment_ready,
        local_payment_channel="maestro_direct" if local_payment_ready else None,
        local_payment_currency="TND" if local_payment_ready else None,
        local_payment_gate_reasons=gate_reasons,
    )


@router.get(
    "/catalog/offers",
    response_model=AdminMarketplaceOfferListResponse,
)
async def list_admin_marketplace_original_offers(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> AdminMarketplaceOfferListResponse:
    try:
        authority = await _commercial_read_authority(
            current_user=current_user,
            runtime=runtime,
        )
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        items = tuple(
            _admin_offer_payload(offer)
            for offer in list_offer_prices(include_unlisted=True)
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc

    return AdminMarketplaceOfferListResponse(
        source="billing.offer_pricebook",
        pricebook_version=OFFER_PRICEBOOK_VERSION,
        pricebook_status=OFFER_PRICEBOOK_STATUS,
        items=items,
        count=len(items),
    )


__all__ = [
    "AdminMarketplaceOfferListResponse",
    "AdminMarketplaceOfferResponse",
    "list_admin_marketplace_original_offers",
]
