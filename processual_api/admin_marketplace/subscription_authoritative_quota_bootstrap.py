from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from processual_api.admin_marketplace.subscription_billing_period import (
    next_anchored_month_boundary,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.billing.maestro_units import normalize_maestro_metric_code


@dataclass(frozen=True, slots=True)
class AuthoritativeQuotaBootstrapInput:
    subscription_id: uuid.UUID
    customer_ref: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    subscription_status: str
    effective_at: datetime
    plan_code: str
    authority_version: str
    entitlement_codes: tuple[str, ...]
    metric_code: str
    base_limit_units: int


@dataclass(frozen=True, slots=True)
class AuthoritativeQuotaBootstrapResult:
    runtime: AdminMarketSubscriptionRuntime
    quota_cycle: AdminMarketSubscriptionQuotaCycle
    replayed: bool


class AuthoritativeQuotaBootstrapUnitOfWork(Protocol):
    subscription_runtime: object
    subscription_quota_cycles: object

    async def __aenter__(self) -> AuthoritativeQuotaBootstrapUnitOfWork: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


def _ref(value: str, name: str) -> str:
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 128:
        raise SubscriptionRuntimeError(f"{name} is invalid.")
    return normalized


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise SubscriptionRuntimeError("runtime effective_at must be timezone-aware.")
    return value.astimezone(UTC)


def _validate(source: AuthoritativeQuotaBootstrapInput) -> tuple[str, str, str, str, str, datetime]:
    customer_ref = _ref(source.customer_ref, "customer reference")
    entitlement_profile_ref = _ref(
        source.entitlement_profile_ref,
        "entitlement profile reference",
    )
    quota_profile_ref = _ref(source.quota_profile_ref, "quota profile reference")
    plan_code = _ref(source.plan_code, "plan code")
    authority_version = _ref(source.authority_version, "quota authority version")
    effective_at = _aware(source.effective_at)
    if source.subscription_status != "active":
        raise SubscriptionRuntimeError(
            "only an active subscription can bootstrap runtime access."
        )
    if isinstance(source.base_limit_units, bool) or source.base_limit_units <= 0:
        raise SubscriptionRuntimeError("authoritative quota limit must be positive.")
    if not source.entitlement_codes or any(
        not code.strip() for code in source.entitlement_codes
    ):
        raise SubscriptionRuntimeError("authoritative entitlement codes are required.")
    return (
        customer_ref,
        entitlement_profile_ref,
        quota_profile_ref,
        plan_code,
        authority_version,
        effective_at,
    )


async def bootstrap_authoritative_quota_in_unit(
    *,
    source: AuthoritativeQuotaBootstrapInput,
    uow: AuthoritativeQuotaBootstrapUnitOfWork,
) -> AuthoritativeQuotaBootstrapResult:
    (
        customer_ref,
        entitlement_profile_ref,
        quota_profile_ref,
        plan_code,
        authority_version,
        effective_at,
    ) = _validate(source)
    metric_code = normalize_maestro_metric_code(source.metric_code)

    runtime = await uow.subscription_runtime.get_by_subscription_id(
        source.subscription_id,
        for_update=True,
    )
    if runtime is not None and (
        runtime.customer_ref != customer_ref
        or runtime.entitlement_profile_ref != entitlement_profile_ref
        or runtime.quota_profile_ref != quota_profile_ref
        or runtime.access_stage != "active"
    ):
        raise SubscriptionRuntimeError(
            "runtime replay conflicts with the authoritative subscription binding."
        )

    existing_cycle = await uow.subscription_quota_cycles.get_current(
        subscription_id=source.subscription_id,
        metric_code=metric_code,
        occurred_at=effective_at,
        for_update=True,
    )
    if existing_cycle is not None:
        if runtime is None:
            raise SubscriptionRuntimeError(
                "quota cycle exists without authoritative runtime access."
            )
        if (
            existing_cycle.customer_ref != customer_ref
            or existing_cycle.plan_code != plan_code
            or existing_cycle.plan_catalog_version != authority_version
            or existing_cycle.quota_profile_ref != quota_profile_ref
            or existing_cycle.base_limit_units != source.base_limit_units
            or tuple(existing_cycle.entitlement_codes) != tuple(source.entitlement_codes)
        ):
            raise SubscriptionRuntimeError(
                "quota cycle replay conflicts with the authoritative quota binding."
            )
        return AuthoritativeQuotaBootstrapResult(
            runtime=runtime,
            quota_cycle=existing_cycle,
            replayed=True,
        )

    if runtime is None:
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
        uow.subscription_runtime.add(runtime)

    cycle = AdminMarketSubscriptionQuotaCycle(
        subscription_id=source.subscription_id,
        source_cycle_id=None,
        customer_ref=customer_ref,
        plan_code=plan_code,
        plan_catalog_version=authority_version,
        entitlement_codes=list(source.entitlement_codes),
        quota_profile_ref=quota_profile_ref,
        metric_code=metric_code,
        period_start=effective_at,
        period_end=next_anchored_month_boundary(
            starts_at=effective_at,
            anchor_day=effective_at.day,
        ),
        base_limit_units=source.base_limit_units,
        rollover_units=0,
        top_up_units=0,
        rollover_status="available",
        used_units=0,
        version=0,
    )
    uow.subscription_quota_cycles.add(cycle)
    return AuthoritativeQuotaBootstrapResult(
        runtime=runtime,
        quota_cycle=cycle,
        replayed=False,
    )


__all__ = [
    "AuthoritativeQuotaBootstrapInput",
    "AuthoritativeQuotaBootstrapResult",
    "AuthoritativeQuotaBootstrapUnitOfWork",
    "bootstrap_authoritative_quota_in_unit",
]
