from __future__ import annotations

import uuid
from typing import Any

from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.subscription_quota_usage import (
    SubscriptionQuotaUsageCommand,
    record_subscription_quota_usage_factory,
)
from processual_api.admin_marketplace.subscription_runtime import build_usage_reservation
from processual_api.db.session import get_session_factory


def _uow_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
    return SqlAlchemyAdminMarketplaceUnitOfWork(get_session_factory())


async def record_sandbox_api_key_usage(
    *,
    current_user: dict[str, Any],
    method: str,
    endpoint: str,
    metric_code: str,
    units: int,
    idempotency_key: str,
):
    """Record metered sandbox API-key usage in the authoritative quota-cycle ledger."""

    if current_user.get("session_type") != "sandbox_api_key":
        raise ValueError("durable sandbox API-key identity required")
    if units <= 0:
        raise ValueError("durable sandbox usage units must be positive")

    try:
        subscription_id = uuid.UUID(str(current_user["subscription_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("durable sandbox subscription identity required") from exc

    customer_ref = str(current_user.get("client_id") or "").strip()
    api_key_id = str(current_user.get("api_key_id") or "").strip()
    if not customer_ref or not api_key_id:
        raise ValueError("durable sandbox customer/key identity required")

    reservation = build_usage_reservation(
        units=units,
        idempotency_key=idempotency_key,
        dimensions={
            "source": "sandbox_api_key",
            "api_key_id": api_key_id,
            "method": method.upper(),
            "endpoint": endpoint,
            "plan_id": str(current_user.get("plan_id") or ""),
            "operational_profile_id": str(
                current_user.get("operational_profile_id") or ""
            ),
            "environment": "sandbox",
        },
    )
    record_usage = record_subscription_quota_usage_factory(
        unit_of_work_factory=_uow_factory
    )
    return await record_usage(
        SubscriptionQuotaUsageCommand(
            subscription_id=subscription_id,
            customer_ref=customer_ref,
            metric_code=metric_code,
            units=units,
            idempotency_key_hash=reservation.idempotency_key_hash,
            dimensions_digest=reservation.dimensions_digest,
            occurred_at=reservation.occurred_at,
            quota_cycle_id=None,
        )
    )


__all__ = ["record_sandbox_api_key_usage"]
