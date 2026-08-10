from __future__ import annotations

from decimal import Decimal

import pytest

from processual_api.billing.usage_economics import (
    DEFAULT_CREDITS_PER_UNIT,
    MarginSnapshot,
    ObservedCostInput,
    UsageMeteringInput,
    build_usage_economics_snapshot,
    forecast_usage_run_rate,
)
from processual_api.services.commercial_operations_read_model import (
    build_commercial_operations_read_model,
)
from processual_api.services.customer_360 import build_customer_360_read_model


def test_units_convert_to_credits_with_explicit_contract() -> None:
    metering = UsageMeteringInput(units=125, credits_per_unit=Decimal("1.5"))
    assert metering.credits == Decimal("187.5000")


def test_default_credit_contract_is_one_to_one_and_visible() -> None:
    assert DEFAULT_CREDITS_PER_UNIT == Decimal("1")
    snapshot = build_usage_economics_snapshot(
        units=12,
        recognized_revenue_usd=Decimal("20"),
    )
    assert snapshot["credits"] == "12.0000"
    assert snapshot["credits_per_unit"] == "1"


def test_metering_rejects_negative_units_and_non_positive_rate() -> None:
    with pytest.raises(ValueError, match="units"):
        UsageMeteringInput(units=-1)
    with pytest.raises(ValueError, match="credits_per_unit"):
        UsageMeteringInput(units=1, credits_per_unit=Decimal("0"))


def test_observed_costs_are_additive_and_never_invented() -> None:
    costs = ObservedCostInput(
        provider_cost_usd=Decimal("2.25"),
        infrastructure_cost_usd=Decimal("1.10"),
        operations_cost_usd=Decimal("0.65"),
    )
    assert costs.total_cost_usd == Decimal("4.0000")


def test_observed_costs_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="provider_cost_usd"):
        ObservedCostInput(provider_cost_usd=Decimal("-0.01"))


def test_margin_engine_uses_explicit_revenue_and_observed_costs() -> None:
    margin = MarginSnapshot(
        recognized_revenue_usd=Decimal("10"),
        costs=ObservedCostInput(
            provider_cost_usd=Decimal("2"),
            infrastructure_cost_usd=Decimal("1"),
            operations_cost_usd=Decimal("1"),
        ),
    )
    assert margin.gross_margin_usd == Decimal("6.0000")
    assert margin.gross_margin_percent == Decimal("60.0000")


def test_zero_revenue_has_no_fake_margin_percentage() -> None:
    margin = MarginSnapshot(
        recognized_revenue_usd=Decimal("0"),
        costs=ObservedCostInput(),
    )
    assert margin.gross_margin_percent is None


def test_usage_run_rate_forecast_projects_units_credits_and_cost() -> None:
    forecast = forecast_usage_run_rate(
        observed_days=10,
        period_days=30,
        units=100,
        credits_per_unit=Decimal("2"),
        observed_cost_usd=Decimal("3.50"),
    )
    assert forecast.projected_units == 300
    assert forecast.projected_credits == Decimal("600.0000")
    assert forecast.projected_cost_usd == Decimal("10.5000")


def test_forecast_rejects_invalid_period_bounds() -> None:
    with pytest.raises(ValueError, match="observed_days"):
        forecast_usage_run_rate(observed_days=0, period_days=30, units=1)
    with pytest.raises(ValueError, match="period_days"):
        forecast_usage_run_rate(observed_days=20, period_days=10, units=1)


def test_snapshot_keeps_byok_provider_cost_boundary_explicit() -> None:
    snapshot = build_usage_economics_snapshot(
        units=40,
        recognized_revenue_usd=Decimal("100"),
        provider_cost_usd=Decimal("12"),
        infrastructure_cost_usd=Decimal("8"),
    )
    assert snapshot["provider_cost_source"] == "observed_input"
    assert snapshot["provider_cost_included_in_maestro_price"] is False
    assert snapshot["total_observed_cost_usd"] == "20.0000"
    assert snapshot["gross_margin_usd"] == "80.0000"


def _customer_model(
    *,
    client_id: str,
    units: int,
    revenue: str,
    cost: str,
    near_limit: bool = False,
    exceeded: bool = False,
) -> dict[str, object]:
    return {
        "client_id": client_id,
        "usage": {"monthly_units_used": units},
        "quota": {"near_limit": near_limit, "exceeded": exceeded},
        "economics": {
            "credits": str(Decimal(units).quantize(Decimal("0.0001"))),
            "recognized_revenue_usd": revenue,
            "total_observed_cost_usd": cost,
        },
    }


def test_customer_360_combines_scoped_usage_economics_and_forecast() -> None:
    summary = {
        "client_id": "client-1",
        "user_id": "user-1",
        "plan": {"plan_id": "starter", "monthly_unit_allowance": 1000},
        "usage": {
            "monthly_units_used": 250,
            "monthly_units_allowance": 1000,
            "monthly_units_remaining": 750,
            "usage_percent": 25.0,
        },
        "quota": {"near_limit": False, "exceeded": False, "status": "ok"},
        "provider": {
            "byok_required": True,
            "provider_cost_included": False,
            "connection_status": "configured",
        },
    }
    model = build_customer_360_read_model(
        client_usage_summary=summary,
        economics_input={
            "recognized_revenue_usd": "50",
            "provider_cost_usd": "5",
            "infrastructure_cost_usd": "10",
            "operations_cost_usd": "2.5",
            "credits_per_unit": "1",
        },
        observed_days=15,
        period_days=30,
    )
    assert model["client_id"] == "client-1"
    assert model["economics"]["credits"] == "250.0000"
    assert model["economics"]["gross_margin_usd"] == "32.5000"
    assert model["forecast"]["projected_units"] == 500
    assert model["transparency"]["usage_source"] == "scoped_usage_ledger"
    assert model["transparency"]["provider_cost_included_in_maestro_price"] is False


def test_customer_360_omits_forecast_when_observation_window_missing() -> None:
    model = build_customer_360_read_model(
        client_usage_summary={"usage": {"monthly_units_used": 0}},
    )
    assert model["forecast"] is None
    assert model["transparency"]["forecast_method"] is None


def test_operations_read_model_aggregates_customer_360_portfolio() -> None:
    model = build_commercial_operations_read_model(
        [
            _customer_model(
                client_id="alpha",
                units=100,
                revenue="30",
                cost="10",
                near_limit=True,
            ),
            _customer_model(
                client_id="beta",
                units=50,
                revenue="20",
                cost="5",
                exceeded=True,
            ),
        ]
    )
    assert model["customer_count"] == 2
    assert model["total_units"] == 150
    assert model["total_credits"] == "150.0000"
    assert model["recognized_revenue_usd"] == "50.0000"
    assert model["total_observed_cost_usd"] == "15.0000"
    assert model["gross_margin_usd"] == "35.0000"
    assert model["gross_margin_percent"] == "70.0000"
    assert model["near_limit_clients"] == ["alpha"]
    assert model["exceeded_clients"] == ["beta"]
    assert model["authority"]["cost_source"] == "observed_inputs_only"


def test_operations_read_model_does_not_invent_margin_percent_without_revenue() -> None:
    model = build_commercial_operations_read_model(
        [_customer_model(client_id="zero", units=0, revenue="0", cost="0")]
    )
    assert model["gross_margin_percent"] is None
