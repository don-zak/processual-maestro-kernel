from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.models import (
    AdminMarketChannelEligibility,
    AdminMarketChannelSelection,
    AdminMarketOrder,
    AdminMarketPlan,
    AdminMarketSubscription,
    AdminMarketTrial,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)


@dataclass(frozen=True, slots=True)
class DashboardTrialReadResult:
    trial_ref: str
    customer_ref: str
    plan_code: str
    status: str
    starts_at: datetime | None
    ends_at: datetime | None


@dataclass(frozen=True, slots=True)
class DashboardSubscriptionReadResult:
    subscription_ref: str
    customer_ref: str
    plan_code: str
    status: str
    starts_at: datetime | None
    ends_at: datetime | None


@dataclass(frozen=True, slots=True)
class DashboardQuotaReadResult:
    subscription_id: str
    customer_ref: str
    plan_code: str
    metric_code: str
    period_start: datetime
    period_end: datetime
    base_limit_units: int
    rollover_units: int
    top_up_units: int
    used_units: int
    remaining_units: int
    rollover_status: str


@dataclass(frozen=True, slots=True)
class DashboardChannelReadResult:
    customer_ref: str
    country_code: str | None
    address_status: str
    maestro_direct_status: str
    lemon_squeezy_status: str
    customer_choice_allowed: bool
    admin_review_required: bool
    restriction_reason: str | None
    automatic_activation_allowed: bool
    selected_channel: str | None
    customer_consented: bool | None
    selection_recorded_at: datetime | None


@dataclass(frozen=True, slots=True)
class DashboardVerifiedOrderValueReadResult:
    currency: str
    verified_order_count: int
    verified_order_value: Decimal


@dataclass(frozen=True, slots=True)
class AdminMarketplaceDashboardReadResult:
    trials: tuple[DashboardTrialReadResult, ...]
    subscriptions: tuple[DashboardSubscriptionReadResult, ...]
    quotas: tuple[DashboardQuotaReadResult, ...]
    channels: tuple[DashboardChannelReadResult, ...]
    verified_order_values: tuple[DashboardVerifiedOrderValueReadResult, ...]


class AdminMarketplaceDashboardReadService:
    """Authority-gated operational read model for the Admin Marketplace UI."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def read(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        limit: int = 100,
    ) -> AdminMarketplaceDashboardReadResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )
        bounded_limit = max(1, min(int(limit), 200))

        async with self._session_factory() as session:
            trials = tuple(
                (
                    await session.execute(
                        select(AdminMarketTrial, AdminMarketPlan.plan_code)
                        .join(AdminMarketPlan, AdminMarketPlan.id == AdminMarketTrial.plan_id)
                        .order_by(AdminMarketTrial.updated_at.desc(), AdminMarketTrial.id.desc())
                        .limit(bounded_limit)
                    )
                ).all()
            )
            subscriptions = tuple(
                (
                    await session.execute(
                        select(AdminMarketSubscription, AdminMarketPlan.plan_code)
                        .join(AdminMarketPlan, AdminMarketPlan.id == AdminMarketSubscription.plan_id)
                        .order_by(
                            AdminMarketSubscription.updated_at.desc(),
                            AdminMarketSubscription.id.desc(),
                        )
                        .limit(bounded_limit)
                    )
                ).all()
            )
            quota_cycles = tuple(
                (
                    await session.scalars(
                        select(AdminMarketSubscriptionQuotaCycle)
                        .order_by(
                            AdminMarketSubscriptionQuotaCycle.period_end.desc(),
                            AdminMarketSubscriptionQuotaCycle.id.desc(),
                        )
                        .limit(bounded_limit)
                    )
                ).all()
            )
            eligibilities = tuple(
                (
                    await session.scalars(
                        select(AdminMarketChannelEligibility)
                        .order_by(
                            AdminMarketChannelEligibility.updated_at.desc(),
                            AdminMarketChannelEligibility.id.desc(),
                        )
                        .limit(bounded_limit)
                    )
                ).all()
            )
            selections = tuple(
                (
                    await session.scalars(
                        select(AdminMarketChannelSelection)
                        .order_by(
                            AdminMarketChannelSelection.created_at.desc(),
                            AdminMarketChannelSelection.id.desc(),
                        )
                        .limit(bounded_limit * 2)
                    )
                ).all()
            )
            verified_orders = tuple(
                (
                    await session.scalars(
                        select(AdminMarketOrder).where(
                            AdminMarketOrder.payment_status == "verified"
                        )
                    )
                ).all()
            )

        latest_selection: dict[str, AdminMarketChannelSelection] = {}
        for selection in selections:
            latest_selection.setdefault(selection.customer_ref, selection)

        verified_totals: dict[str, list[Decimal]] = defaultdict(list)
        for order in verified_orders:
            verified_totals[order.currency].append(Decimal(order.total_amount))

        return AdminMarketplaceDashboardReadResult(
            trials=tuple(
                DashboardTrialReadResult(
                    trial_ref=trial.trial_ref,
                    customer_ref=trial.customer_ref,
                    plan_code=plan_code,
                    status=trial.status,
                    starts_at=trial.starts_at,
                    ends_at=trial.ends_at,
                )
                for trial, plan_code in trials
            ),
            subscriptions=tuple(
                DashboardSubscriptionReadResult(
                    subscription_ref=subscription.subscription_ref,
                    customer_ref=subscription.customer_ref,
                    plan_code=plan_code,
                    status=subscription.status,
                    starts_at=subscription.starts_at,
                    ends_at=subscription.ends_at,
                )
                for subscription, plan_code in subscriptions
            ),
            quotas=tuple(
                DashboardQuotaReadResult(
                    subscription_id=str(cycle.subscription_id),
                    customer_ref=cycle.customer_ref,
                    plan_code=cycle.plan_code,
                    metric_code=cycle.metric_code,
                    period_start=cycle.period_start,
                    period_end=cycle.period_end,
                    base_limit_units=cycle.base_limit_units,
                    rollover_units=cycle.spendable_rollover_units,
                    top_up_units=cycle.top_up_units,
                    used_units=cycle.used_units,
                    remaining_units=cycle.available_units,
                    rollover_status=cycle.rollover_status,
                )
                for cycle in quota_cycles
            ),
            channels=tuple(
                _channel_result(
                    eligibility,
                    latest_selection.get(eligibility.customer_ref),
                )
                for eligibility in eligibilities
            ),
            verified_order_values=tuple(
                DashboardVerifiedOrderValueReadResult(
                    currency=currency,
                    verified_order_count=len(values),
                    verified_order_value=sum(values, Decimal("0.000")),
                )
                for currency, values in sorted(verified_totals.items())
            ),
        )


def _channel_result(
    eligibility: AdminMarketChannelEligibility,
    selection: AdminMarketChannelSelection | None,
) -> DashboardChannelReadResult:
    return DashboardChannelReadResult(
        customer_ref=eligibility.customer_ref,
        country_code=eligibility.country_code,
        address_status=eligibility.address_status,
        maestro_direct_status=eligibility.maestro_direct_status,
        lemon_squeezy_status=eligibility.lemon_squeezy_status,
        customer_choice_allowed=eligibility.customer_choice_allowed,
        admin_review_required=eligibility.admin_review_required,
        restriction_reason=eligibility.restriction_reason,
        automatic_activation_allowed=eligibility.automatic_activation_allowed,
        selected_channel=None if selection is None else selection.selected_channel,
        customer_consented=None if selection is None else selection.customer_consented,
        selection_recorded_at=None if selection is None else selection.created_at,
    )


__all__ = [
    "AdminMarketplaceDashboardReadResult",
    "AdminMarketplaceDashboardReadService",
    "DashboardChannelReadResult",
    "DashboardQuotaReadResult",
    "DashboardSubscriptionReadResult",
    "DashboardTrialReadResult",
    "DashboardVerifiedOrderValueReadResult",
]
