from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Self

from processual_api.admin_marketplace.models import AdminMarketSubscription
from processual_api.admin_marketplace.subscription_delinquency_persistence import (
    AdminMarketSubscriptionDelinquency,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime_access_policy import (
    SubscriptionRuntimeAccessError,
    advance_expired_runtime_stage,
    runtime_allows_usage,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)


class SubscriptionQuotaUsageError(RuntimeError):
    """Quota usage cannot be recorded safely."""


@dataclass(frozen=True, slots=True)
class SubscriptionQuotaUsageCommand:
    subscription_id: uuid.UUID
    quota_cycle_id: uuid.UUID
    customer_ref: str
    metric_code: str
    units: int
    idempotency_key_hash: str
    dimensions_digest: str
    occurred_at: datetime


class _SubscriptionRepository(Protocol):
    async def get_by_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscription | None: ...


class _SubscriptionRuntimeRepository(Protocol):
    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionRuntime | None: ...


class _SubscriptionQuotaCycleRepository(Protocol):
    async def get_by_id(
        self,
        cycle_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaCycle | None: ...


class _SubscriptionQuotaCycleUsageRepository(Protocol):
    async def get_by_idempotency_hash(
        self,
        value: str,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaCycleUsage | None: ...

    async def sum_units_since(
        self,
        *,
        quota_cycle_id: uuid.UUID,
        occurred_at: datetime,
    ) -> int: ...

    def add(self, usage: AdminMarketSubscriptionQuotaCycleUsage) -> None: ...


class _SubscriptionDelinquencyRepository(Protocol):
    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionDelinquency | None: ...


class SubscriptionQuotaUsageUnitOfWork(Protocol):
    @property
    def subscriptions(self) -> _SubscriptionRepository: ...

    @property
    def subscription_runtime(self) -> _SubscriptionRuntimeRepository: ...

    @property
    def subscription_quota_cycles(self) -> _SubscriptionQuotaCycleRepository: ...

    @property
    def subscription_quota_cycle_usage(self) -> _SubscriptionQuotaCycleUsageRepository: ...

    @property
    def subscription_delinquency(self) -> _SubscriptionDelinquencyRepository: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


def record_subscription_quota_usage_factory(
    *,
    unit_of_work_factory: Callable[[], SubscriptionQuotaUsageUnitOfWork],
):
    async def record(
        command: SubscriptionQuotaUsageCommand,
    ) -> AdminMarketSubscriptionQuotaCycleUsage:
        _validate(command)
        async with unit_of_work_factory() as uow:
            existing = await uow.subscription_quota_cycle_usage.get_by_idempotency_hash(
                command.idempotency_key_hash,
                for_update=True,
            )
            if existing is not None:
                _assert_replay_matches(command, existing)
                return existing

            subscription = await uow.subscriptions.get_by_id(
                command.subscription_id,
                for_update=True,
            )
            if subscription is None or subscription.status != "active":
                raise SubscriptionQuotaUsageError(
                    "quota usage requires an active subscription."
                )
            if subscription.customer_ref != command.customer_ref:
                raise SubscriptionQuotaUsageError(
                    "quota usage customer conflicts with subscription."
                )

            runtime = await uow.subscription_runtime.get_by_subscription_id(
                command.subscription_id,
                for_update=True,
            )
            if runtime is None:
                raise SubscriptionQuotaUsageError(
                    "quota usage requires authoritative runtime access."
                )
            if runtime.customer_ref != command.customer_ref:
                raise SubscriptionQuotaUsageError(
                    "quota usage customer conflicts with runtime."
                )

            try:
                expired = advance_expired_runtime_stage(
                    runtime,
                    evaluated_at=command.occurred_at,
                )
                allowed = runtime_allows_usage(
                    runtime,
                    occurred_at=command.occurred_at,
                )
            except SubscriptionRuntimeAccessError as exc:
                raise SubscriptionQuotaUsageError(str(exc)) from exc

            if not allowed:
                if expired:
                    await uow.commit()
                raise SubscriptionQuotaUsageError(
                    "quota usage is blocked by runtime access stage."
                )

            cycle = await uow.subscription_quota_cycles.get_by_id(
                command.quota_cycle_id,
                for_update=True,
            )
            if cycle is None:
                raise SubscriptionQuotaUsageError("quota cycle was not found.")
            if (
                cycle.subscription_id != command.subscription_id
                or cycle.customer_ref != command.customer_ref
                or cycle.metric_code != command.metric_code
            ):
                raise SubscriptionQuotaUsageError(
                    "quota cycle conflicts with usage command."
                )
            if not cycle.period_start <= command.occurred_at < cycle.period_end:
                raise SubscriptionQuotaUsageError(
                    "quota usage falls outside the selected cycle."
                )

            if runtime.access_stage == "grace":
                await _enforce_degraded_grace_cap(
                    uow=uow,
                    command=command,
                    cycle=cycle,
                    runtime=runtime,
                )

            if command.units > cycle.available_units:
                raise SubscriptionQuotaUsageError("quota balance is insufficient.")

            cycle.used_units += command.units
            cycle.version += 1
            usage = AdminMarketSubscriptionQuotaCycleUsage(
                quota_cycle_id=cycle.id,
                subscription_id=cycle.subscription_id,
                customer_ref=cycle.customer_ref,
                metric_code=cycle.metric_code,
                units=command.units,
                idempotency_key_hash=command.idempotency_key_hash,
                dimensions_digest=command.dimensions_digest,
                occurred_at=command.occurred_at,
            )
            uow.subscription_quota_cycle_usage.add(usage)
            await uow.commit()
            return usage

    return record


async def _enforce_degraded_grace_cap(
    *,
    uow: SubscriptionQuotaUsageUnitOfWork,
    command: SubscriptionQuotaUsageCommand,
    cycle: AdminMarketSubscriptionQuotaCycle,
    runtime: AdminMarketSubscriptionRuntime,
) -> None:
    delinquency = await uow.subscription_delinquency.get_by_subscription_id(
        command.subscription_id,
        for_update=True,
    )
    if delinquency is None or delinquency.state != "grace_degraded":
        raise SubscriptionQuotaUsageError(
            "grace usage requires authoritative delinquency state."
        )
    if delinquency.customer_ref != command.customer_ref:
        raise SubscriptionQuotaUsageError(
            "grace usage customer conflicts with delinquency state."
        )

    grace_started_at = delinquency.grace_started_at
    grace_until = delinquency.grace_until
    if (
        grace_started_at is None
        or grace_started_at.tzinfo is None
        or grace_until is None
        or grace_until.tzinfo is None
        or runtime.grace_until != grace_until
    ):
        raise SubscriptionQuotaUsageError(
            "grace usage requires consistent timezone-aware deadlines."
        )
    if not grace_started_at <= command.occurred_at < grace_until:
        raise SubscriptionQuotaUsageError(
            "quota usage falls outside the degraded grace window."
        )

    grace_cap = cycle.base_limit_units * delinquency.grace_usage_percent // 100
    consumed_in_grace = await uow.subscription_quota_cycle_usage.sum_units_since(
        quota_cycle_id=cycle.id,
        occurred_at=grace_started_at,
    )
    if consumed_in_grace + command.units > grace_cap:
        raise SubscriptionQuotaUsageError(
            "degraded grace usage cap is exhausted."
        )


def _validate(command: SubscriptionQuotaUsageCommand) -> None:
    if command.units <= 0:
        raise ValueError("quota usage units must be positive.")
    if command.occurred_at.tzinfo is None:
        raise ValueError("quota usage timestamp must be timezone-aware.")
    if len(command.idempotency_key_hash) != 64:
        raise ValueError("quota usage idempotency hash must contain 64 characters.")
    if len(command.dimensions_digest) != 64:
        raise ValueError("quota usage dimensions digest must contain 64 characters.")


def _assert_replay_matches(
    command: SubscriptionQuotaUsageCommand,
    existing: AdminMarketSubscriptionQuotaCycleUsage,
) -> None:
    if (
        existing.quota_cycle_id != command.quota_cycle_id
        or existing.subscription_id != command.subscription_id
        or existing.customer_ref != command.customer_ref
        or existing.metric_code != command.metric_code
        or existing.units != command.units
        or existing.dimensions_digest != command.dimensions_digest
        or existing.occurred_at != command.occurred_at
    ):
        raise SubscriptionQuotaUsageError(
            "quota usage replay conflicts with the existing ledger entry."
        )


__all__ = [
    "SubscriptionQuotaUsageCommand",
    "SubscriptionQuotaUsageError",
    "SubscriptionQuotaUsageUnitOfWork",
    "record_subscription_quota_usage_factory",
]
