"""Stage 3 usage, credits, cost, margin, and forecasting contracts.

All monetary inputs are observed or explicitly supplied. The module never calls
providers, fetches price lists, or invents missing commercial cost assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

USAGE_ECONOMICS_VERSION: Final = "2026-08-b3-usage-economics-v1"
DEFAULT_CREDITS_PER_UNIT: Final = Decimal("1")
MONEY_QUANTUM: Final = Decimal("0.0001")


def _decimal(value: Decimal | int | str | float) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class UsageMeteringInput:
    units: int
    credits_per_unit: Decimal = DEFAULT_CREDITS_PER_UNIT

    def __post_init__(self) -> None:
        if self.units < 0:
            raise ValueError("units must not be negative")
        if self.credits_per_unit <= 0:
            raise ValueError("credits_per_unit must be positive")

    @property
    def credits(self) -> Decimal:
        return _money(Decimal(self.units) * self.credits_per_unit)


@dataclass(frozen=True, slots=True)
class ObservedCostInput:
    provider_cost_usd: Decimal = Decimal("0")
    infrastructure_cost_usd: Decimal = Decimal("0")
    operations_cost_usd: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for name, value in (
            ("provider_cost_usd", self.provider_cost_usd),
            ("infrastructure_cost_usd", self.infrastructure_cost_usd),
            ("operations_cost_usd", self.operations_cost_usd),
        ):
            if value < 0:
                raise ValueError(f"{name} must not be negative")

    @property
    def total_cost_usd(self) -> Decimal:
        return _money(
            self.provider_cost_usd
            + self.infrastructure_cost_usd
            + self.operations_cost_usd
        )


@dataclass(frozen=True, slots=True)
class MarginSnapshot:
    recognized_revenue_usd: Decimal
    costs: ObservedCostInput

    def __post_init__(self) -> None:
        if self.recognized_revenue_usd < 0:
            raise ValueError("recognized_revenue_usd must not be negative")

    @property
    def gross_margin_usd(self) -> Decimal:
        return _money(self.recognized_revenue_usd - self.costs.total_cost_usd)

    @property
    def gross_margin_percent(self) -> Decimal | None:
        if self.recognized_revenue_usd == 0:
            return None
        return _money(
            (self.gross_margin_usd / self.recognized_revenue_usd) * Decimal("100")
        )


@dataclass(frozen=True, slots=True)
class UsageForecast:
    observed_days: int
    period_days: int
    observed_units: int
    observed_credits: Decimal
    observed_cost_usd: Decimal
    projected_units: int
    projected_credits: Decimal
    projected_cost_usd: Decimal


def forecast_usage_run_rate(
    *,
    observed_days: int,
    period_days: int,
    units: int,
    credits_per_unit: Decimal = DEFAULT_CREDITS_PER_UNIT,
    observed_cost_usd: Decimal = Decimal("0"),
) -> UsageForecast:
    if observed_days <= 0:
        raise ValueError("observed_days must be positive")
    if period_days < observed_days:
        raise ValueError("period_days must be >= observed_days")
    if observed_cost_usd < 0:
        raise ValueError("observed_cost_usd must not be negative")

    metering = UsageMeteringInput(units=units, credits_per_unit=credits_per_unit)
    factor = Decimal(period_days) / Decimal(observed_days)
    projected_units = int(
        (Decimal(units) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    projected_credits = _money(metering.credits * factor)
    projected_cost = _money(observed_cost_usd * factor)

    return UsageForecast(
        observed_days=observed_days,
        period_days=period_days,
        observed_units=units,
        observed_credits=metering.credits,
        observed_cost_usd=_money(observed_cost_usd),
        projected_units=projected_units,
        projected_credits=projected_credits,
        projected_cost_usd=projected_cost,
    )


def build_usage_economics_snapshot(
    *,
    units: int,
    recognized_revenue_usd: Decimal,
    provider_cost_usd: Decimal = Decimal("0"),
    infrastructure_cost_usd: Decimal = Decimal("0"),
    operations_cost_usd: Decimal = Decimal("0"),
    credits_per_unit: Decimal = DEFAULT_CREDITS_PER_UNIT,
) -> dict[str, object]:
    metering = UsageMeteringInput(units=units, credits_per_unit=credits_per_unit)
    costs = ObservedCostInput(
        provider_cost_usd=provider_cost_usd,
        infrastructure_cost_usd=infrastructure_cost_usd,
        operations_cost_usd=operations_cost_usd,
    )
    margin = MarginSnapshot(recognized_revenue_usd=recognized_revenue_usd, costs=costs)
    return {
        "version": USAGE_ECONOMICS_VERSION,
        "units": units,
        "credits": str(metering.credits),
        "credits_per_unit": str(credits_per_unit),
        "recognized_revenue_usd": str(_money(recognized_revenue_usd)),
        "provider_cost_usd": str(_money(provider_cost_usd)),
        "provider_cost_source": "observed_input",
        "provider_cost_included_in_maestro_price": False,
        "infrastructure_cost_usd": str(_money(infrastructure_cost_usd)),
        "operations_cost_usd": str(_money(operations_cost_usd)),
        "total_observed_cost_usd": str(costs.total_cost_usd),
        "gross_margin_usd": str(margin.gross_margin_usd),
        "gross_margin_percent": (
            str(margin.gross_margin_percent)
            if margin.gross_margin_percent is not None
            else None
        ),
    }


__all__ = [
    "DEFAULT_CREDITS_PER_UNIT",
    "MarginSnapshot",
    "ObservedCostInput",
    "USAGE_ECONOMICS_VERSION",
    "UsageForecast",
    "UsageMeteringInput",
    "build_usage_economics_snapshot",
    "forecast_usage_run_rate",
]
