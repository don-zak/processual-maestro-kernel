from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from processual_api.admin_marketplace.commercial_offer_projection import (
    COMMERCIAL_OFFER_PROJECTION_VERSION,
    CommercialOfferProjection,
)

COMMERCIAL_OFFER_PROVENANCE_VERSION: Final = "2026-08-admin-market-offer-provenance-v1"
AUTHORITATIVE_PRICING_CURRENCY: Final = "USD"


@dataclass(frozen=True, slots=True)
class CommercialOfferProvenance:
    provenance_version: str
    projection_version: str
    offer_code: str
    plan_code: str
    sales_channel: str
    billing_period: str
    source_offer_id: str
    source_pricebook_version: str
    source_pricing_version: str
    authoritative_price_currency: str
    authoritative_price_amount: str
    settlement_currency: str
    settlement_amount: str
    exchange_rate_value: str | None
    exchange_rate_source: str | None
    exchange_rate_reference: str | None
    exchange_rate_observed_at: str | None
    exchange_rate_expires_at: str | None
    generated_at: str

    def __post_init__(self) -> None:
        if self.provenance_version != COMMERCIAL_OFFER_PROVENANCE_VERSION:
            raise ValueError("commercial offer provenance version is invalid")
        if self.projection_version != COMMERCIAL_OFFER_PROJECTION_VERSION:
            raise ValueError("commercial offer projection version is invalid")
        if self.authoritative_price_currency != AUTHORITATIVE_PRICING_CURRENCY:
            raise ValueError("authoritative offer pricing currency must be USD")
        for field_name in (
            "offer_code",
            "plan_code",
            "sales_channel",
            "billing_period",
            "source_offer_id",
            "source_pricebook_version",
            "source_pricing_version",
            "settlement_currency",
            "generated_at",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} must not be blank")
        for field_name in ("authoritative_price_amount", "settlement_amount"):
            value = Decimal(str(getattr(self, field_name)))
            if not value.is_finite() or value <= 0:
                raise ValueError(f"{field_name} must be positive and finite")
        if self.sales_channel == "maestro_direct":
            required_fx = (
                self.exchange_rate_value,
                self.exchange_rate_source,
                self.exchange_rate_reference,
                self.exchange_rate_observed_at,
                self.exchange_rate_expires_at,
            )
            if any(value is None or not str(value).strip() for value in required_fx):
                raise ValueError("Maestro Direct provenance requires complete FX evidence")
            rate = Decimal(str(self.exchange_rate_value))
            if not rate.is_finite() or rate <= 0:
                raise ValueError("Maestro Direct provenance FX rate is invalid")
        elif self.sales_channel == "lemon_squeezy":
            if any(
                value is not None
                for value in (
                    self.exchange_rate_value,
                    self.exchange_rate_source,
                    self.exchange_rate_reference,
                    self.exchange_rate_observed_at,
                    self.exchange_rate_expires_at,
                )
            ):
                raise ValueError("Lemon Squeezy provenance must not contain FX evidence")
        else:
            raise ValueError("unsupported provenance sales channel")

    def payload(self) -> dict[str, str | None]:
        return asdict(self)

    def digest_sha256(self) -> str:
        encoded = json.dumps(
            self.payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def build_offer_provenance(
    *,
    projection: CommercialOfferProjection,
    generated_at: datetime,
) -> CommercialOfferProvenance:
    if generated_at.tzinfo is None:
        raise ValueError("offer provenance generated_at must be timezone-aware")

    return CommercialOfferProvenance(
        provenance_version=COMMERCIAL_OFFER_PROVENANCE_VERSION,
        projection_version=COMMERCIAL_OFFER_PROJECTION_VERSION,
        offer_code=projection.offer_code,
        plan_code=projection.plan_code,
        sales_channel=projection.sales_channel,
        billing_period=projection.billing_period,
        source_offer_id=projection.source_offer_id,
        source_pricebook_version=projection.source_pricebook_version,
        source_pricing_version=projection.source_pricing_version,
        authoritative_price_currency=AUTHORITATIVE_PRICING_CURRENCY,
        authoritative_price_amount=str(projection.authoritative_price_usd),
        settlement_currency=projection.currency,
        settlement_amount=str(projection.amount),
        exchange_rate_value=(
            None
            if projection.exchange_rate_value is None
            else str(projection.exchange_rate_value)
        ),
        exchange_rate_source=projection.exchange_rate_source,
        exchange_rate_reference=projection.exchange_rate_reference,
        exchange_rate_observed_at=(
            None
            if projection.exchange_rate_observed_at is None
            else projection.exchange_rate_observed_at.isoformat()
        ),
        exchange_rate_expires_at=(
            None
            if projection.exchange_rate_expires_at is None
            else projection.exchange_rate_expires_at.isoformat()
        ),
        generated_at=generated_at.isoformat(),
    )


__all__ = [
    "AUTHORITATIVE_PRICING_CURRENCY",
    "COMMERCIAL_OFFER_PROVENANCE_VERSION",
    "CommercialOfferProvenance",
    "build_offer_provenance",
]
