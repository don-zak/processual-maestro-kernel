from __future__ import annotations

import uuid
from typing import Any, Protocol

from processual_api.auth.models import AuthRegistrationPlanIntent
from processual_api.billing.public_plan_journey import (
    public_plan_journey_catalog,
)


class SubscriptionPreparationRepository(Protocol):
    async def registration_plan_intent_for_user(
        self,
        *,
        user_id: uuid.UUID,
    ) -> AuthRegistrationPlanIntent | None: ...


async def build_subscription_preparation(
    *,
    repository: SubscriptionPreparationRepository,
    user_id: uuid.UUID,
) -> dict[str, object]:
    intent = await repository.registration_plan_intent_for_user(
        user_id=user_id
    )

    if intent is None:
        return {
            "status": "no_intent",
            "checkout_available": False,
        }

    if intent.state == "pending_verification":
        return {
            "status": "pending_verification",
            "checkout_available": False,
        }

    if intent.state != "verified":
        return {
            "status": "invalid_intent",
            "checkout_available": False,
        }

    billing_period = intent.billing_period
    if billing_period not in {"monthly", "annual"}:
        return {
            "status": "invalid_intent",
            "checkout_available": False,
        }

    catalog = public_plan_journey_catalog()
    raw_plans = catalog.get("plans", [])
    plans = raw_plans if isinstance(raw_plans, list) else []

    plan: dict[str, Any] | None = next(
        (
            candidate
            for candidate in plans
            if isinstance(candidate, dict)
            and candidate.get("plan_id") == intent.selected_plan_id
        ),
        None,
    )

    if (
        plan is None
        or bool(plan.get("requires_assessment"))
        or not bool(plan.get("registration_available"))
    ):
        return {
            "status": "invalid_intent",
            "checkout_available": False,
        }

    price_key = (
        "monthly_price_usd"
        if billing_period == "monthly"
        else "annual_price_usd"
    )
    price = plan.get(price_key)

    if price is None:
        return {
            "status": "invalid_intent",
            "checkout_available": False,
        }

    return {
        "status": "verified",
        "plan_id": intent.selected_plan_id,
        "billing_period": billing_period,
        "display_name": plan.get("display_name"),
        "price_usd": price,
        "currency": catalog.get("currency", "USD"),
        "included_quota_units": plan.get("included_quota_units"),
        "checkout_available": bool(
            catalog.get("checkout_enabled", False)
        ),
    }


__all__ = [
    "SubscriptionPreparationRepository",
    "build_subscription_preparation",
]
