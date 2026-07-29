"""Commercial currency and fixed-settlement contracts for Group 2.

All Maestro commercial catalog prices remain authoritative in USD.

Lemon Squeezy settles in USD. Eligible Tunisia-local purchases settle in TND
using a fixed, auditable USD/TND quote captured for the individual order.

This module defines contracts and pure validation only. It does not perform
network access, create orders, mutate balances, or activate commercial runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Protocol, runtime_checkable

from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)

COMMERCIAL_CURRENCY_SETTLEMENT_VERSION: Final = "2026-07-group2-usd-tnd-settlement-v1"
COMMERCIAL_CURRENCY_SETTLEMENT_STATUS: Final = "draft_review"

AUTHORITATIVE_PRICING_CURRENCY: Final = "USD"
LOCAL_TUNISIA_SETTLEMENT_CURRENCY: Final = "TND"

USD_QUANTUM: Final = Decimal("0.01")
TND_QUANTUM: Final = Decimal("0.001")

EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED: Final = False
LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED: Final = False


@dataclass(frozen=True, slots=True)
class ExchangeRateQuote:
    """Immutable USD/TND exchange-rate quote for one purchase operation."""

    base_currency: str
    settlement_currency: str
    rate: Decimal
    source: str
    reference: str
    observed_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        normalized_base = self.base_currency.strip().upper()
        normalized_settlement = self.settlement_currency.strip().upper()

        if normalized_base != AUTHORITATIVE_PRICING_CURRENCY:
            raise ValueError("exchange-rate base currency must be USD")

        if normalized_settlement != LOCAL_TUNISIA_SETTLEMENT_CURRENCY:
            raise ValueError("exchange-rate settlement currency must be TND")

        if not isinstance(self.rate, Decimal):
            raise TypeError("exchange rate must use Decimal")

        if not self.rate.is_finite():
            raise ValueError("exchange rate must be finite")

        if self.rate <= 0:
            raise ValueError("exchange rate must be positive")

        if not self.source.strip():
            raise ValueError("exchange-rate source must not be blank")

        if not self.reference.strip():
            raise ValueError("exchange-rate reference must not be blank")

        if self.observed_at.tzinfo is None:
            raise ValueError("exchange-rate observed_at must be timezone-aware")

        if self.expires_at.tzinfo is None:
            raise ValueError("exchange-rate expires_at must be timezone-aware")

        if self.expires_at <= self.observed_at:
            raise ValueError("exchange-rate expires_at must be after observed_at")

        object.__setattr__(self, "base_currency", normalized_base)
        object.__setattr__(
            self,
            "settlement_currency",
            normalized_settlement,
        )
        object.__setattr__(self, "source", self.source.strip())
        object.__setattr__(self, "reference", self.reference.strip())

    def is_expired_at(self, instant: datetime) -> bool:
        """Return whether the quote is expired at a timezone-aware instant."""

        if instant.tzinfo is None:
            raise ValueError("quote comparison instant must be timezone-aware")

        return instant >= self.expires_at


@runtime_checkable
class ExchangeRateProviderPort(Protocol):
    """Port for obtaining auditable fixed USD/TND quotes."""

    async def quote_usd_to_tnd(
        self,
        *,
        requested_at: datetime,
    ) -> ExchangeRateQuote:
        """Return a fixed USD/TND quote for an eligible local purchase."""


def calculate_tnd_settlement(
    *,
    amount_usd: Decimal,
    usd_tnd_rate: Decimal,
) -> Decimal:
    """Convert an authoritative USD price into a rounded TND settlement."""

    _require_positive_finite_decimal(
        amount_usd,
        field_name="amount_usd",
    )
    _require_positive_finite_decimal(
        usd_tnd_rate,
        field_name="usd_tnd_rate",
    )

    return (amount_usd * usd_tnd_rate).quantize(
        TND_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def validate_channel_settlement(
    *,
    channel: TopUpCheckoutChannel,
    total_price_usd: Decimal,
    settlement_currency: str,
    settlement_amount: Decimal,
    exchange_rate_quote: ExchangeRateQuote | None,
) -> None:
    """Validate channel-aware settlement values and fail closed."""

    _require_positive_finite_decimal(
        total_price_usd,
        field_name="total_price_usd",
    )
    _require_positive_finite_decimal(
        settlement_amount,
        field_name="settlement_amount",
    )

    normalized_currency = settlement_currency.strip().upper()

    if channel is TopUpCheckoutChannel.LEMON_SQUEEZY:
        if normalized_currency != AUTHORITATIVE_PRICING_CURRENCY:
            raise ValueError("Lemon Squeezy settlement currency must be USD")

        expected_amount = total_price_usd.quantize(
            USD_QUANTUM,
            rounding=ROUND_HALF_UP,
        )
        actual_amount = settlement_amount.quantize(
            USD_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

        if actual_amount != expected_amount:
            raise ValueError("Lemon Squeezy settlement amount must equal USD order price")

        if exchange_rate_quote is not None:
            raise ValueError("Lemon Squeezy settlement must not include exchange-rate data")

        return

    if channel is TopUpCheckoutChannel.LOCAL_TUNISIA:
        if normalized_currency != LOCAL_TUNISIA_SETTLEMENT_CURRENCY:
            raise ValueError("Tunisia-local settlement currency must be TND")

        if exchange_rate_quote is None:
            raise ValueError("Tunisia-local settlement requires an exchange-rate quote")

        expected_amount = calculate_tnd_settlement(
            amount_usd=total_price_usd,
            usd_tnd_rate=exchange_rate_quote.rate,
        )
        actual_amount = settlement_amount.quantize(
            TND_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

        if actual_amount != expected_amount:
            raise ValueError("Tunisia-local settlement amount does not match fixed quote")

        return

    raise ValueError("unsupported top-up checkout channel")


def build_currency_settlement_status() -> dict[str, bool | str]:
    """Return safe, non-secret status for the settlement foundation."""

    return {
        "contract_version": COMMERCIAL_CURRENCY_SETTLEMENT_VERSION,
        "status": COMMERCIAL_CURRENCY_SETTLEMENT_STATUS,
        "authoritative_pricing_currency": (AUTHORITATIVE_PRICING_CURRENCY),
        "local_tunisia_settlement_currency": (LOCAL_TUNISIA_SETTLEMENT_CURRENCY),
        "exchange_rate_provider_runtime_enabled": (EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED),
        "local_tunisia_settlement_runtime_enabled": (LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED),
        "fail_closed_by_default": True,
    }


def _require_positive_finite_decimal(
    value: Decimal,
    *,
    field_name: str,
) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must use Decimal")

    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")

    if value <= 0:
        raise ValueError(f"{field_name} must be positive")


__all__ = [
    "AUTHORITATIVE_PRICING_CURRENCY",
    "COMMERCIAL_CURRENCY_SETTLEMENT_STATUS",
    "COMMERCIAL_CURRENCY_SETTLEMENT_VERSION",
    "EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED",
    "ExchangeRateProviderPort",
    "ExchangeRateQuote",
    "LOCAL_TUNISIA_SETTLEMENT_CURRENCY",
    "LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED",
    "TND_QUANTUM",
    "USD_QUANTUM",
    "build_currency_settlement_status",
    "calculate_tnd_settlement",
    "validate_channel_settlement",
]
