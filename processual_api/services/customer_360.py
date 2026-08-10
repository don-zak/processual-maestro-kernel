"""Customer 360 read model for Stage 3 usage transparency and economics."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Final

from processual_api.billing.usage_economics import (
    DEFAULT_CREDITS_PER_UNIT,
    build_usage_economics_snapshot,
    forecast_usage_run_rate,
)

CUSTOMER_360_VERSION: Final = "2026-08-b3-customer-360-v1"


def _int(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _decimal(payload: dict[str, Any], key: str) -> Decimal:
    try:
        return Decimal(str(payload.get(key) or "0"))
    except Exception:
        return Decimal("0")


def build_customer_360_read_model(
    *,
    client_usage_summary: dict[str, Any],
    economics_input: dict[str, Any] | None = None,
    observed_days: int | None = None,
    period_days: int = 30,
) -> dict[str, object]:
    summary = client_usage_summary if isinstance(client_usage_summary, dict) else {}
    economics = economics_input if isinstance(economics_input, dict) else {}
    usage = summary.get("usage") if isinstance(summary.get("usage"), dict) else {}
    plan = summary.get("plan") if isinstance(summary.get("plan"), dict) else {}
    quota = summary.get("quota") if isinstance(summary.get("quota"), dict) else {}
    provider = summary.get("provider") if isinstance(summary.get("provider"), dict) else {}

    units = _int(usage, "monthly_units_used")
    credits_per_unit = _decimal(economics, "credits_per_unit") or DEFAULT_CREDITS_PER_UNIT
    snapshot = build_usage_economics_snapshot(
        units=units,
        credits_per_unit=credits_per_unit,
        recognized_revenue_usd=_decimal(economics, "recognized_revenue_usd"),
        provider_cost_usd=_decimal(economics, "provider_cost_usd"),
        infrastructure_cost_usd=_decimal(economics, "infrastructure_cost_usd"),
        operations_cost_usd=_decimal(economics, "operations_cost_usd"),
    )

    forecast = None
    if observed_days is not None:
        result = forecast_usage_run_rate(
            observed_days=observed_days,
            period_days=period_days,
            units=units,
            credits_per_unit=credits_per_unit,
            observed_cost_usd=Decimal(str(snapshot["total_observed_cost_usd"])),
        )
        forecast = {
            "observed_days": result.observed_days,
            "period_days": result.period_days,
            "projected_units": result.projected_units,
            "projected_credits": str(result.projected_credits),
            "projected_cost_usd": str(result.projected_cost_usd),
        }

    return {
        "version": CUSTOMER_360_VERSION,
        "client_id": str(summary.get("client_id") or ""),
        "user_id": str(summary.get("user_id") or ""),
        "plan": plan,
        "usage": usage,
        "quota": quota,
        "provider": provider,
        "economics": snapshot,
        "forecast": forecast,
        "transparency": {
            "usage_source": "scoped_usage_ledger",
            "credits_conversion_visible": True,
            "provider_cost_source": "observed_input",
            "provider_cost_included_in_maestro_price": False,
            "margin_inputs_explicit": True,
            "forecast_method": "linear_run_rate" if forecast is not None else None,
        },
    }


__all__ = ["CUSTOMER_360_VERSION", "build_customer_360_read_model"]
