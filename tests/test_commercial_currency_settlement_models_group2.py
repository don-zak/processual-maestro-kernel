from sqlalchemy import CheckConstraint, Numeric

from processual_api.billing.commercial_top_up_models import (
    CommercialTopUpOrder,
    CommercialTopUpPaymentEvidence,
)


def test_order_exposes_fixed_settlement_columns() -> None:
    table = CommercialTopUpOrder.__table__

    assert table.c.total_price_usd.type.precision == 18
    assert table.c.total_price_usd.type.scale == 2

    assert table.c.settlement_currency.type.length == 3

    assert isinstance(table.c.settlement_amount.type, Numeric)
    assert table.c.settlement_amount.type.precision == 18
    assert table.c.settlement_amount.type.scale == 3
    assert table.c.settlement_amount.nullable is False

    assert isinstance(table.c.exchange_rate_usd_tnd.type, Numeric)
    assert table.c.exchange_rate_usd_tnd.type.precision == 18
    assert table.c.exchange_rate_usd_tnd.type.scale == 6

    assert table.c.exchange_rate_source.type.length == 255
    assert table.c.exchange_rate_reference.type.length == 255

    assert table.c.exchange_rate_observed_at.type.timezone is True
    assert table.c.exchange_rate_expires_at.type.timezone is True


def test_order_has_channel_aware_settlement_constraints() -> None:
    table = CommercialTopUpOrder.__table__

    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    def check_by_suffix(suffix: str) -> str:
        matches = [sqltext for name, sqltext in checks.items() if name is not None and name.endswith(suffix)]

        assert len(matches) == 1
        return matches[0]

    check_by_suffix("settlement_currency_allowed")
    check_by_suffix("settlement_amount_positive")
    channel_check = check_by_suffix("channel_settlement_consistent")

    assert "channel = 'lemon_squeezy'" in channel_check
    assert "settlement_currency = 'USD'" in channel_check
    assert "settlement_amount = total_price_usd" in channel_check

    assert "channel = 'local_tunisia'" in channel_check
    assert "settlement_currency = 'TND'" in channel_check
    assert "exchange_rate_usd_tnd IS NOT NULL" in channel_check
    assert "exchange_rate_expires_at" in channel_check
    assert "exchange_rate_observed_at" in channel_check


def test_payment_evidence_uses_currency_neutral_amount() -> None:
    table = CommercialTopUpPaymentEvidence.__table__

    assert "verified_amount" in table.c
    assert "verified_amount_usd" not in table.c

    amount_type = table.c.verified_amount.type

    assert isinstance(amount_type, Numeric)
    assert amount_type.precision == 18
    assert amount_type.scale == 3


def test_payment_amount_constraint_uses_generic_column() -> None:
    table = CommercialTopUpPaymentEvidence.__table__

    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    amount_matches = [
        sqltext for name, sqltext in checks.items() if name is not None and name.endswith("verified_amount_positive")
    ]

    assert len(amount_matches) == 1
    amount_check = amount_matches[0]

    assert "verified_amount IS NULL" in amount_check
    assert "verified_amount > 0" in amount_check
    assert "verified_amount_usd" not in amount_check
