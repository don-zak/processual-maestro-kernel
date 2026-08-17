from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final

from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateQuote,
    calculate_tnd_settlement,
)
from processual_api.billing.offer_pricebook import list_offer_prices

COMMERCIAL_OFFER_PROJECTION_VERSION: Final = "2026-08-admin-market-offer-projection-v1"


@dataclass(frozen=True, slots=True)
class CommercialOfferProjection:
    offer_code: str
    plan_code: str
    display_name: str
    sales_channel: str
    billing_period: str
    currency: str
    amount: Decimal
    authoritative_price_usd: Decimal
    status: str
    effective_at: datetime | None
    expires_at: datetime | None
    customer_specific: bool
    source_offer_id: str
    source_pricebook_version: str
    source_pricing_version: str
    exchange_rate_source: str | None = None
    exchange_rate_reference: str | None = None
    exchange_rate_observed_at: datetime | None = None
    exchange_rate_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status != "draft":
            raise ValueError("offer projection must remain draft")
        if self.sales_channel not in {"lemon_squeezy", "maestro_direct"}:
            raise ValueError("unsupported offer projection channel")
        if self.billing_period not in {"monthly", "annual"}:
            raise ValueError("offer projection billing period is invalid")
        if self.sales_channel == "lemon_squeezy" and self.currency != "USD":
            raise ValueError("Lemon Squeezy draft offers must remain USD")
        if self.sales_channel == "maestro_direct" and self.currency != "TND":
            raise ValueError("Maestro Direct draft offers must settle in TND")
        if not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("offer projection amount must be positive and finite")
        if not self.authoritative_price_usd.is_finite() or self.authoritative_price_usd <= 0:
            raise ValueError("authoritative USD price must be positive and finite")
        if self.sales_channel == "lemon_squeezy" and self.amount != self.authoritative_price_usd:
            raise ValueError("Lemon Squeezy amount must equal authoritative USD price")


def _checkout_candidates() -> dict[tuple[str, str], dict[str, object]]:
    candidates: dict[tuple[str, str], dict[str, object]] = {}
    for offer in list_offer_prices(include_unlisted=True):
        period = str(offer["billing_interval"])
        if period not in {"monthly", "annual"}:
            continue
        if bool(offer["requires_sales_contact"]):
            continue
        candidates[(str(offer["plan_id"]), period)] = offer
    return candidates


def _usd_amount(offer: dict[str, object], billing_period: str) -> Decimal:
    key = "monthly_amount_cents" if billing_period == "monthly" else "annual_amount_cents"
    cents = offer.get(key)
    if not isinstance(cents, int) or cents <= 0:
        raise ValueError("canonical offer is missing an approved selected-pricing amount")
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"))


def build_lemon_squeezy_draft_offer_projections() -> tuple[CommercialOfferProjection, ...]:
    projections: list[CommercialOfferProjection] = []
    for (plan_code, period), offer in _checkout_candidates().items():
        amount_usd = _usd_amount(offer, period)
        projections.append(
            CommercialOfferProjection(
                offer_code=f"{plan_code}_{period}_lemon_draft",
                plan_code=plan_code,
                display_name=f"{offer['plan_display_name']} {period.title()} — Lemon Squeezy",
                sales_channel="lemon_squeezy",
                billing_period=period,
                currency="USD",
                amount=amount_usd,
                authoritative_price_usd=amount_usd,
                status="draft",
                effective_at=None,
                expires_at=None,
                customer_specific=False,
                source_offer_id=str(offer["offer_id"]),
                source_pricebook_version=str(offer["pricebook_version"]),
                source_pricing_version=str(offer["pricing_source_version"]),
            )
        )
    return tuple(projections)


def build_maestro_direct_draft_offer_projection(
    *,
    plan_code: str,
    billing_period: str,
    exchange_rate_quote: ExchangeRateQuote,
) -> CommercialOfferProjection:
    normalized_plan = plan_code.strip().lower()
    normalized_period = billing_period.strip().lower()
    offer = _checkout_candidates().get((normalized_plan, normalized_period))
    if offer is None:
        raise ValueError("plan is not eligible for direct checkout projection")

    amount_usd = _usd_amount(offer, normalized_period)
    amount_tnd = calculate_tnd_settlement(
        amount_usd=amount_usd,
        usd_tnd_rate=exchange_rate_quote.rate,
    )
    return CommercialOfferProjection(
        offer_code=f"{normalized_plan}_{normalized_period}_tn_draft",
        plan_code=normalized_plan,
        display_name=f"{offer['plan_display_name']} {normalized_period.title()} — Tunisia",
        sales_channel="maestro_direct",
        billing_period=normalized_period,
        currency="TND",
        amount=amount_tnd,
        authoritative_price_usd=amount_usd,
        status="draft",
        effective_at=None,
        expires_at=None,
        customer_specific=False,
        source_offer_id=str(offer["offer_id"]),
        source_pricebook_version=str(offer["pricebook_version"]),
        source_pricing_version=str(offer["pricing_source_version"]),
        exchange_rate_source=exchange_rate_quote.source,
        exchange_rate_reference=exchange_rate_quote.reference,
        exchange_rate_observed_at=exchange_rate_quote.observed_at,
        exchange_rate_expires_at=exchange_rate_quote.expires_at,
    )


__all__ = [
    "COMMERCIAL_OFFER_PROJECTION_VERSION",
    "CommercialOfferProjection",
    "build_lemon_squeezy_draft_offer_projections",
    "build_maestro_direct_draft_offer_projection",
]
