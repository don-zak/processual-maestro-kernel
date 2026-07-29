import ast
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from processual_api.billing.commercial_currency_settlement_contracts import (
    ExchangeRateQuote,
    calculate_tnd_settlement,
)

MODULE_PATH = Path("processual_api/billing/commercial_currency_settlement_contracts.py")


@pytest.mark.parametrize(
    ("amount", "rate"),
    [
        (Decimal("0"), Decimal("3.1")),
        (Decimal("-1"), Decimal("3.1")),
        (Decimal("1"), Decimal("0")),
        (Decimal("1"), Decimal("-3.1")),
        (Decimal("NaN"), Decimal("3.1")),
        (Decimal("Infinity"), Decimal("3.1")),
    ],
)
def test_non_positive_or_non_finite_values_are_rejected(
    amount: Decimal,
    rate: Decimal,
) -> None:
    with pytest.raises(ValueError):
        calculate_tnd_settlement(
            amount_usd=amount,
            usd_tnd_rate=rate,
        )


@pytest.mark.parametrize(
    ("amount", "rate"),
    [
        (49.0, Decimal("3.1")),
        (Decimal("49"), 3.1),
    ],
)
def test_float_money_values_are_rejected(
    amount: object,
    rate: object,
) -> None:
    with pytest.raises(TypeError):
        calculate_tnd_settlement(  # type: ignore[arg-type]
            amount_usd=amount,
            usd_tnd_rate=rate,
        )


def test_exchange_quote_rejects_naive_timestamps() -> None:
    observed_at = datetime(2026, 7, 29, 16, 0)

    with pytest.raises(
        ValueError,
        match="observed_at must be timezone-aware",
    ):
        ExchangeRateQuote(
            base_currency="USD",
            settlement_currency="TND",
            rate=Decimal("3.1"),
            source="source",
            reference="reference",
            observed_at=observed_at,
            expires_at=observed_at + timedelta(minutes=30),
        )


def test_exchange_quote_rejects_invalid_expiry_order() -> None:
    observed_at = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="expires_at must be after observed_at",
    ):
        ExchangeRateQuote(
            base_currency="USD",
            settlement_currency="TND",
            rate=Decimal("3.1"),
            source="source",
            reference="reference",
            observed_at=observed_at,
            expires_at=observed_at,
        )


@pytest.mark.parametrize(
    ("base_currency", "settlement_currency"),
    [
        ("EUR", "TND"),
        ("USD", "EUR"),
    ],
)
def test_exchange_quote_fails_closed_for_other_currencies(
    base_currency: str,
    settlement_currency: str,
) -> None:
    observed_at = datetime(2026, 7, 29, 16, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        ExchangeRateQuote(
            base_currency=base_currency,
            settlement_currency=settlement_currency,
            rate=Decimal("3.1"),
            source="source",
            reference="reference",
            observed_at=observed_at,
            expires_at=observed_at + timedelta(minutes=30),
        )


def test_contract_has_no_network_or_database_dependencies() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8-sig"))

    imported_roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])

    assert imported_roots.isdisjoint(
        {
            "httpx",
            "requests",
            "sqlalchemy",
            "redis",
            "aiohttp",
        }
    )


def test_runtime_flags_remain_literal_false() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    expected_flags = {
        "EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED",
        "LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED",
    }

    assignments: dict[str, object] = {}

    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue

        if not isinstance(node.target, ast.Name):
            continue

        if node.target.id not in expected_flags:
            continue

        assert isinstance(node.value, ast.Constant)
        assignments[node.target.id] = node.value.value

    assert assignments == {
        "EXCHANGE_RATE_PROVIDER_RUNTIME_ENABLED": False,
        "LOCAL_TUNISIA_SETTLEMENT_RUNTIME_ENABLED": False,
    }
