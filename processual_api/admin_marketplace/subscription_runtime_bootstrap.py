from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from processual_api.admin_marketplace.subscription_billing_period import quota_period_end
from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaProfile,
    validate_quota_profile,
)
from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionQuotaAccount,
    AdminMarketSubscriptionRuntime,
)


@dataclass(frozen=True, slots=True)
class SubscriptionRuntimeBootstrapInput:
    subscription_id: uuid.UUID
    customer_ref: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    subscription_status: str
    effective_at: datetime


@dataclass(frozen=True, slots=True)
class SubscriptionRuntimeBootstrapResult:
    runtime: AdminMarketSubscriptionRuntime
    quota_accounts: tuple[AdminMarketSubscriptionQuotaAccount, ...]
    replayed: bool


class SubscriptionRuntimeRepository(Protocol):
    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionRuntime | None: ...

    def add(self, runtime: AdminMarketSubscriptionRuntime) -> None: ...


class SubscriptionQuotaRepository(Protocol):
    async def get_current(
        self,
        *,
        subscription_id: uuid.UUID,
        metric_code: str,
        occurred_at: datetime,
        for_update: bool = False,
    ) -> AdminMarketSubscriptionQuotaAccount | None: ...

    def add(self, account: AdminMarketSubscriptionQuotaAccount) -> None: ...


class SubscriptionRuntimeBootstrapUnitOfWork(Protocol):
    subscription_runtime: SubscriptionRuntimeRepository
    subscription_quotas: SubscriptionQuotaRepository

    async def __aenter__(self) -> SubscriptionRuntimeBootstrapUnitOfWork: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


def _require_ref(value: str, name: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 128:
        raise SubscriptionRuntimeError(f"{name} is invalid.")
    return normalized


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise SubscriptionRuntimeError("runtime effective_at must be timezone-aware.")
    return value.astimezone(UTC)


async def bootstrap_subscription_runtime_in_unit(
    *,
    source: SubscriptionRuntimeBootstrapInput,
    quota_profile: SubscriptionQuotaProfile,
    uow: SubscriptionRuntimeBootstrapUnitOfWork,
) -> SubscriptionRuntimeBootstrapResult:
    """Bootstrap runtime state without owning the surrounding transaction."""

    customer_ref = _require_ref(source.customer_ref, "customer reference")
    entitlement_profile_ref = _require_ref(
        source.entitlement_profile_ref,
        "entitlement profile reference",
    )
    quota_profile_ref = _require_ref(
        source.quota_profile_ref,
        "quota profile reference",
    )
    effective_at = _require_aware(source.effective_at)
    profile = validate_quota_profile(quota_profile)

    if source.subscription_status != "active":
        raise SubscriptionRuntimeError(
            "only an active subscription can bootstrap runtime access."
        )
    if profile.profile_ref != quota_profile_ref:
        raise SubscriptionRuntimeError("quota profile binding mismatch.")

    existing = await uow.subscription_runtime.get_by_subscription_id(
        source.subscription_id,
        for_update=True,
    )
    if existing is not None:
        if (
            existing.customer_ref != customer_ref
            or existing.entitlement_profile_ref != entitlement_profile_ref
            or existing.quota_profile_ref != quota_profile_ref
            or existing.access_stage != "active"
        ):
            raise SubscriptionRuntimeError(
                "runtime replay conflicts with the original subscription binding."
            )
        accounts = []
        for metric in profile.metrics:
            account = await uow.subscription_quotas.get_current(
                subscription_id=source.subscription_id,
                metric_code=metric.metric_code,
                occurred_at=effective_at,
                for_update=True,
            )
            if account is None:
                raise SubscriptionRuntimeError(
                    "runtime replay is missing an expected quota account."
                )
            if (
                account.customer_ref != customer_ref
                or account.quota_profile_ref != quota_profile_ref
                or account.limit_units != metric.limit_units
            ):
                raise SubscriptionRuntimeError(
                    "quota replay conflicts with the original profile binding."
                )
            accounts.append(account)
        return SubscriptionRuntimeBootstrapResult(
            runtime=existing,
            quota_accounts=tuple(accounts),
            replayed=True,
        )

    runtime = AdminMarketSubscriptionRuntime(
        id=uuid.uuid4(),
        subscription_id=source.subscription_id,
        customer_ref=customer_ref,
        entitlement_profile_ref=entitlement_profile_ref,
        quota_profile_ref=quota_profile_ref,
        access_stage="active",
        version=0,
        effective_at=effective_at,
    )
    period_end = quota_period_end(
        starts_at=effective_at,
        period_days=profile.period_days,
    )
    accounts = tuple(
        AdminMarketSubscriptionQuotaAccount(
            id=uuid.uuid4(),
            subscription_id=source.subscription_id,
            customer_ref=customer_ref,
            quota_profile_ref=quota_profile_ref,
            metric_code=metric.metric_code,
            period_start=effective_at,
            period_end=period_end,
            limit_units=metric.limit_units,
            used_units=0,
            version=0,
        )
        for metric in profile.metrics
    )
    uow.subscription_runtime.add(runtime)
    for account in accounts:
        uow.subscription_quotas.add(account)
    return SubscriptionRuntimeBootstrapResult(
        runtime=runtime,
        quota_accounts=accounts,
        replayed=False,
    )


def bootstrap_subscription_runtime_factory(
    *,
    uow_factory: Callable[[], SubscriptionRuntimeBootstrapUnitOfWork],
):
    async def bootstrap(
        *,
        source: SubscriptionRuntimeBootstrapInput,
        quota_profile: SubscriptionQuotaProfile,
    ) -> SubscriptionRuntimeBootstrapResult:
        async with uow_factory() as uow:
            result = await bootstrap_subscription_runtime_in_unit(
                source=source,
                quota_profile=quota_profile,
                uow=uow,
            )
            if not result.replayed:
                await uow.commit()
            return result

    return bootstrap


__all__ = [
    "SubscriptionQuotaRepository",
    "SubscriptionRuntimeBootstrapInput",
    "SubscriptionRuntimeBootstrapResult",
    "SubscriptionRuntimeBootstrapUnitOfWork",
    "SubscriptionRuntimeRepository",
    "bootstrap_subscription_runtime_factory",
    "bootstrap_subscription_runtime_in_unit",
]
