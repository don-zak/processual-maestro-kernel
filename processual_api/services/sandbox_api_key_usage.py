from __future__ import annotations

import uuid
from typing import Any

from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.admin_marketplace.subscription_usage_service import (
    record_subscription_usage_factory,
)
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
    """Record metered sandbox API-key usage in the durable subscription ledger.

    The caller must already have authenticated the key through durable sandbox
    authority. Subscription/customer identity is therefore taken from that
    authenticated identity rather than from request payloads or Settings JSON.
    """

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

    record_usage = record_subscription_usage_factory(uow_factory=_uow_factory)
    return await record_usage(
        subscription_id=subscription_id,
        customer_ref=customer_ref,
        metric_code=metric_code,
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


__all__ = ["record_sandbox_api_key_usage"]
