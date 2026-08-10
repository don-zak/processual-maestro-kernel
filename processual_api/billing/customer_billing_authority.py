from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_top_up_grant_persistence import (
    AdminMarketSubscriptionTopUpGrant,
)
from processual_api.billing.commercial_top_up_models import CommercialTopUpOrder
from processual_api.billing.maestro_units import (
    LEGACY_CREDIT_METRIC,
    MAESTRO_UNIT_METRIC,
    normalize_maestro_metric_code,
)
from processual_api.db.session import get_session_factory


class BillingAuthorityError(RuntimeError):
    """Authoritative billing inputs cannot be reconciled safely."""


def _period_bounds(period: str) -> tuple[datetime, datetime]:
    try:
        year_text, month_text = str(period).split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        raise BillingAuthorityError("billing period must use YYYY-MM") from None

    start = datetime(year, month, 1, tzinfo=UTC)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(year, month + 1, 1, tzinfo=UTC)
    return start, end


def _decimal_text(value: Decimal | None, places: str = "0.01") -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal(places)))


def _cycle_payload(cycle: AdminMarketSubscriptionQuotaCycle) -> dict[str, Any]:
    metric = normalize_maestro_metric_code(cycle.metric_code)
    if metric != MAESTRO_UNIT_METRIC:
        raise BillingAuthorityError("quota cycle does not resolve to Maestro Units")
    return {
        "cycle_id": str(cycle.id),
        "subscription_id": str(cycle.subscription_id),
        "customer_ref": cycle.customer_ref,
        "plan_code": cycle.plan_code,
        "plan_catalog_version": cycle.plan_catalog_version,
        "metric_code": MAESTRO_UNIT_METRIC,
        "period_start": cycle.period_start.isoformat(),
        "period_end": cycle.period_end.isoformat(),
        "base_limit_units": int(cycle.base_limit_units),
        "rollover_units": int(cycle.spendable_rollover_units),
        "top_up_units": int(cycle.top_up_units),
        "used_units": int(cycle.used_units),
        "available_units": int(cycle.available_units),
    }


def _top_up_payload(
    *,
    grant: AdminMarketSubscriptionTopUpGrant,
    order: CommercialTopUpOrder,
) -> dict[str, Any]:
    if order.state != "granted":
        raise BillingAuthorityError("top-up order is not in granted state")
    if grant.order_id != order.id or grant.units != order.requested_units:
        raise BillingAuthorityError("top-up grant conflicts with its purchase order")
    if order.bundle_count <= 0 or order.requested_units % order.bundle_count != 0:
        raise BillingAuthorityError("top-up purchase has invalid bundle geometry")

    return {
        "purchase_ref": str(order.id),
        "grant_ref": str(grant.id),
        "provider_reference": grant.provider_reference,
        "plan_code": order.plan_code,
        "plan_catalog_version": order.plan_catalog_version,
        "purchased_at": order.created_at.isoformat(),
        "granted_at": grant.granted_at.isoformat(),
        "expires_at": grant.expires_at.isoformat(),
        "bundle_units": int(order.requested_units // order.bundle_count),
        "bundle_count": int(order.bundle_count),
        "units_added": int(grant.units),
        "total_price_usd": _decimal_text(order.total_price_usd),
        "settlement_currency": order.settlement_currency,
        "settlement_amount": _decimal_text(order.settlement_amount, "0.001"),
        "channel": order.channel,
        "exchange_rate_usd_tnd": _decimal_text(order.exchange_rate_usd_tnd, "0.000001"),
        "exchange_rate_source": order.exchange_rate_source,
        "exchange_rate_reference": order.exchange_rate_reference,
    }


async def load_billing_authority_snapshot(
    *,
    client_id: str,
    period: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load exactly one authoritative quota cycle and its granted top-ups."""
    start, end = _period_bounds(period)
    session_factory = get_session_factory()

    async with session_factory() as session:
        cycle_stmt = select(AdminMarketSubscriptionQuotaCycle).where(
            AdminMarketSubscriptionQuotaCycle.customer_ref == client_id,
            AdminMarketSubscriptionQuotaCycle.metric_code.in_(
                (MAESTRO_UNIT_METRIC, LEGACY_CREDIT_METRIC)
            ),
            AdminMarketSubscriptionQuotaCycle.period_start == start,
            AdminMarketSubscriptionQuotaCycle.period_end == end,
        )
        cycles = list((await session.scalars(cycle_stmt)).all())
        if len(cycles) != 1:
            raise BillingAuthorityError(
                "billing statement requires exactly one authoritative quota cycle"
            )
        cycle = cycles[0]

        grant_stmt = (
            select(AdminMarketSubscriptionTopUpGrant, CommercialTopUpOrder)
            .join(
                CommercialTopUpOrder,
                CommercialTopUpOrder.id == AdminMarketSubscriptionTopUpGrant.order_id,
            )
            .where(
                AdminMarketSubscriptionTopUpGrant.quota_cycle_id == cycle.id,
                AdminMarketSubscriptionTopUpGrant.customer_ref == client_id,
            )
            .order_by(AdminMarketSubscriptionTopUpGrant.granted_at.asc())
        )
        rows = list((await session.execute(grant_stmt)).all())

    top_ups = [
        _top_up_payload(grant=grant, order=order)
        for grant, order in rows
    ]
    granted_units = sum(item["units_added"] for item in top_ups)
    if granted_units != int(cycle.top_up_units):
        raise BillingAuthorityError(
            "granted top-up detail does not reconcile to authoritative cycle top-up units"
        )

    return _cycle_payload(cycle), top_ups


__all__ = [
    "BillingAuthorityError",
    "load_billing_authority_snapshot",
]
