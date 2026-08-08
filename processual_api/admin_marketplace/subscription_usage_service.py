from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionQuotaAccountState,
    SubscriptionRuntimeError,
    build_usage_reservation,
    reserve_quota_units,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionUsageLedger,
)


class SubscriptionUsageUnitOfWork(Protocol):
    subscription_runtime: object
    subscription_quotas: object
    subscription_usage: object

    async def __aenter__(self) -> SubscriptionUsageUnitOfWork: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


def record_subscription_usage_factory(
    *,
    uow_factory: Callable[[], SubscriptionUsageUnitOfWork],
):
    async def record_usage(
        *,
        subscription_id: uuid.UUID,
        customer_ref: str,
        metric_code: str,
        units: int,
        idempotency_key: str,
        dimensions: dict[str, object],
        occurred_at=None,
    ) -> AdminMarketSubscriptionUsageLedger:
        reservation = build_usage_reservation(
            units=units,
            idempotency_key=idempotency_key,
            dimensions=dimensions,
            occurred_at=occurred_at,
        )

        async with uow_factory() as uow:
            existing = await uow.subscription_usage.get_by_idempotency_hash(
                reservation.idempotency_key_hash,
                for_update=True,
            )
            if existing is not None:
                if (
                    existing.subscription_id != subscription_id
                    or existing.customer_ref != customer_ref
                    or existing.metric_code != metric_code
                    or existing.units != units
                    or existing.dimensions_digest != reservation.dimensions_digest
                ):
                    raise SubscriptionRuntimeError(
                        "usage idempotency replay conflicts with the original binding."
                    )
                return existing

            runtime = await uow.subscription_runtime.get_by_subscription_id(
                subscription_id,
                for_update=True,
            )
            if runtime is None:
                raise SubscriptionRuntimeError("subscription runtime was not found.")
            if runtime.customer_ref != customer_ref:
                raise SubscriptionRuntimeError("subscription customer binding mismatch.")
            if runtime.access_stage not in {"active", "grace"}:
                raise SubscriptionRuntimeError("subscription does not allow usage.")

            quota = await uow.subscription_quotas.get_current(
                subscription_id=subscription_id,
                metric_code=metric_code,
                occurred_at=reservation.occurred_at,
                for_update=True,
            )
            if quota is None:
                raise SubscriptionRuntimeError("quota account was not found.")
            if quota.customer_ref != customer_ref:
                raise SubscriptionRuntimeError("quota customer binding mismatch.")
            if quota.quota_profile_ref != runtime.quota_profile_ref:
                raise SubscriptionRuntimeError("quota profile binding mismatch.")

            quota_state = SubscriptionQuotaAccountState(
                id=quota.id,
                subscription_id=quota.subscription_id,
                customer_ref=quota.customer_ref,
                quota_profile_ref=quota.quota_profile_ref,
                metric_code=quota.metric_code,
                period_start=quota.period_start,
                period_end=quota.period_end,
                limit_units=quota.limit_units,
                used_units=quota.used_units,
                version=quota.version,
            )
            reserve_quota_units(quota_state, reservation=reservation)
            quota.used_units = quota_state.used_units
            quota.version = quota_state.version

            usage = AdminMarketSubscriptionUsageLedger(
                id=uuid.uuid4(),
                quota_account_id=quota.id,
                subscription_id=subscription_id,
                customer_ref=customer_ref,
                metric_code=metric_code,
                units=reservation.units,
                idempotency_key_hash=reservation.idempotency_key_hash,
                dimensions_digest=reservation.dimensions_digest,
                occurred_at=reservation.occurred_at,
            )
            uow.subscription_usage.add(usage)
            await uow.commit()
            return usage

    return record_usage
