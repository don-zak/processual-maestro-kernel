"""Administrative portfolio read model for Stage 3 commercial operations."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any, Final

COMMERCIAL_OPERATIONS_READ_MODEL_VERSION: Final = "2026-08-b3-operations-read-model-v1"


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")


def _int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def build_commercial_operations_read_model(
    customers: Iterable[dict[str, Any]],
) -> dict[str, object]:
    rows = [item for item in customers if isinstance(item, dict)]
    total_units = 0
    total_credits = Decimal("0")
    total_revenue = Decimal("0")
    total_cost = Decimal("0")
    near_limit_clients: list[str] = []
    exceeded_clients: list[str] = []

    for customer in rows:
        usage = customer.get("usage") if isinstance(customer.get("usage"), dict) else {}
        quota = customer.get("quota") if isinstance(customer.get("quota"), dict) else {}
        economics = (
            customer.get("economics")
            if isinstance(customer.get("economics"), dict)
            else {}
        )
        client_id = str(customer.get("client_id") or "")

        total_units += _int(usage.get("monthly_units_used"))
        total_credits += _decimal(economics.get("credits"))
        total_revenue += _decimal(economics.get("recognized_revenue_usd"))
        total_cost += _decimal(economics.get("total_observed_cost_usd"))

        if bool(quota.get("near_limit")) and client_id:
            near_limit_clients.append(client_id)
        if bool(quota.get("exceeded")) and client_id:
            exceeded_clients.append(client_id)

    gross_margin = total_revenue - total_cost
    gross_margin_percent = None
    if total_revenue > 0:
        gross_margin_percent = (gross_margin / total_revenue * Decimal("100")).quantize(
            Decimal("0.0001")
        )

    return {
        "version": COMMERCIAL_OPERATIONS_READ_MODEL_VERSION,
        "customer_count": len(rows),
        "total_units": total_units,
        "total_credits": str(total_credits.quantize(Decimal("0.0001"))),
        "recognized_revenue_usd": str(total_revenue.quantize(Decimal("0.0001"))),
        "total_observed_cost_usd": str(total_cost.quantize(Decimal("0.0001"))),
        "gross_margin_usd": str(gross_margin.quantize(Decimal("0.0001"))),
        "gross_margin_percent": (
            str(gross_margin_percent) if gross_margin_percent is not None else None
        ),
        "near_limit_clients": sorted(near_limit_clients),
        "exceeded_clients": sorted(exceeded_clients),
        "authority": {
            "usage_source": "customer_360_scoped_usage_ledger",
            "cost_source": "observed_inputs_only",
            "provider_cost_included_in_maestro_price": False,
        },
    }


__all__ = [
    "COMMERCIAL_OPERATIONS_READ_MODEL_VERSION",
    "build_commercial_operations_read_model",
]
