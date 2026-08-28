from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from processual_api.billing.commercial_currency_settlement_contracts import (
    AUTHORITATIVE_PRICING_CURRENCY,
    EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED,
    LOCAL_TUNISIA_SETTLEMENT_CURRENCY,
    LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED,
    ExchangeRateQuote,
    build_currency_settlement_status,
    calculate_tnd_settlement,
    validate_channel_settlement,
)
from processual_api.billing.commercial_settings_top_up_checkout_contracts import (
    TopUpCheckoutChannel,
)


def _quote(
    *,
    rate: Decimal = Decimal("3.125000"),
) -> ExchangeRateQuote:
    observed_at = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)
    return ExchangeRateQuote(
        base_currency="usd",
        settlement_currency="tnd",
        rate=rate,
        source="approved-test-source",
        reference="quote-test-001",
        observed_at=observed_at,
        expires_at=observed_at + timedelta(minutes=30),
    )


def test_currency_constants_are_governed() -> None:
    assert AUTHORITATIVE_PRICING_CURRENCY == "USD"
    assert LOCAL_TUNISIA_SETTLEMENT_CURRENCY == "TND"
    assert EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED is False
    assert LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED is False


def test_exchange_rate_quote_normalizes_currencies() -> None:
    quote = _quote()

    assert quote.base_currency == "USD"
    assert quote.settlement_currency == "TND"
    assert quote.source == "approved-test-source"
    assert quote.reference == "quote-test-001"


def test_exchange_rate_quote_expiry_is_inclusive() -> None:
    quote = _quote()

    assert quote.is_expired_at(quote.expires_at) is True
    assert quote.is_expired_at(quote.expires_at - timedelta(microseconds=1)) is False


def test_calculate_tnd_settlement_uses_three_decimal_places() -> None:
    result = calculate_tnd_settlement(
        amount_usd=Decimal("49.00"),
        usd_tnd_rate=Decimal("3.125000"),
    )

    assert result == Decimal("153.125")


def test_calculate_tnd_settlement_uses_half_up_rounding() -> None:
    result = calculate_tnd_settlement(
        amount_usd=Decimal("1.00"),
        usd_tnd_rate=Decimal("3.1235"),
    )

    assert result == Decimal("3.124")


def test_lemon_squeezy_accepts_usd_without_quote() -> None:
    validate_channel_settlement(
        channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
        total_price_usd=Decimal("49.00"),
        settlement_currency="USD",
        settlement_amount=Decimal("49.00"),
        exchange_rate_quote=None,
    )


def test_lemon_squeezy_rejects_tnd() -> None:
    with pytest.raises(
        ValueError,
        match="Lemon Squeezy settlement currency must be USD",
    ):
        validate_channel_settlement(
            channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
            total_price_usd=Decimal("49.00"),
            settlement_currency="TND",
            settlement_amount=Decimal("153.125"),
            exchange_rate_quote=_quote(),
        )


def test_lemon_squeezy_rejects_exchange_quote() -> None:
    with pytest.raises(
        ValueError,
        match="must not include exchange-rate data",
    ):
        validate_channel_settlement(
            channel=TopUpCheckoutChannel.LEMON_SQUEEZY,
            total_price_usd=Decimal("49.00"),
            settlement_currency="USD",
            settlement_amount=Decimal("49.00"),
            exchange_rate_quote=_quote(),
        )


def test_local_tunisia_accepts_fixed_tnd_quote() -> None:
    quote = _quote()

    validate_channel_settlement(
        channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
        total_price_usd=Decimal("49.00"),
        settlement_currency="TND",
        settlement_amount=Decimal("153.125"),
        exchange_rate_quote=quote,
    )


def test_local_tunisia_rejects_missing_quote() -> None:
    with pytest.raises(
        ValueError,
        match="requires an exchange-rate quote",
    ):
        validate_channel_settlement(
            channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
            total_price_usd=Decimal("49.00"),
            settlement_currency="TND",
            settlement_amount=Decimal("153.125"),
            exchange_rate_quote=None,
        )


def test_local_tunisia_rejects_wrong_fixed_amount() -> None:
    with pytest.raises(
        ValueError,
        match="does not match fixed quote",
    ):
        validate_channel_settlement(
            channel=TopUpCheckoutChannel.LOCAL_TUNISIA,
            total_price_usd=Decimal("49.00"),
            settlement_currency="TND",
            settlement_amount=Decimal("153.126"),
            exchange_rate_quote=_quote(),
        )


def test_runtime_status_is_qualified_but_fail_closed() -> None:
    status = build_currency_settlement_status()

    assert status == {
        "contract_version": ("2026-07-group2-usd-tnd-settlement-v1"),
        "status": "qualified_fail_closed",
        "authoritative_pricing_currency": "USD",
        "local_tunisia_settlement_currency": "TND",
        "exchange_rate_provider_runtime_enabled": False,
        "local_tunisia_settlement_runtime_enabled": False,
        "fail_closed_by_default": True,
    }
