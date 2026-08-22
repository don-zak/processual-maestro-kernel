from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
    build_subscription_quota_profiles,
)
from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaMetric,
    SubscriptionQuotaProfile,
)
from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError
from processual_api.admin_marketplace.subscription_runtime_bootstrap import (
    SubscriptionRuntimeBootstrapInput,
    bootstrap_subscription_runtime_factory,
    bootstrap_subscription_runtime_in_unit,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
)


class RuntimeRepository:
    def __init__(self) -> None:
        self.existing = None
        self.added = []
        self.calls = []

    async def get_by_subscription_id(self, subscription_id, *, for_update=False):
        self.calls.append((subscription_id, for_update))
        return self.existing

    def add(self, value):
        self.added.append(value)


class QuotaCycleRepository:
    def __init__(self) -> None:
        self.current = None
        self.added = []
        self.calls = []

    async def get_current(
        self,
        *,
        subscription_id,
        metric_code,
        occurred_at,
        for_update=False,
    ):
        self.calls.append(
            (subscription_id, metric_code, occurred_at, for_update)
        )
        return self.current

    def add(self, value):
        self.added.append(value)


class Uow:
    def __init__(self) -> None:
        self.subscription_runtime = RuntimeRepository()
        self.subscription_quota_cycles = QuotaCycleRepository()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commit_count += 1


def _projection(plan_code: str = "starter"):
    return next(
        item
        for item in build_commercial_plan_projections()
        if item.plan_code == plan_code
    )


def _profile(plan_code: str = "starter") -> SubscriptionQuotaProfile:
    projection = _projection(plan_code)
    return next(
        item
        for item in build_subscription_quota_profiles()
        if item.profile_ref == projection.quota_profile_ref
    )


def _source(*, plan_code: str = "starter", **overrides):
    projection = _projection(plan_code)
    values = dict(
        subscription_id=uuid.uuid4(),
        customer_ref="customer-1",
        entitlement_profile_ref=projection.entitlement_profile_ref,
        quota_profile_ref=projection.quota_profile_ref,
        subscription_status="active",
        effective_at=datetime(2026, 8, 5, tzinfo=UTC),
    )
    values.update(overrides)
    return SubscriptionRuntimeBootstrapInput(**values)


@pytest.mark.asyncio
async def test_bootstrap_creates_runtime_and_authoritative_quota_cycle_with_one_commit() -> None:
    uow = Uow()
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)
    source = _source()
    projection = _projection()

    result = await service(source=source, quota_profile=_profile())

    assert result.replayed is False
    assert uow.commit_count == 1
    assert uow.subscription_runtime.calls == [(source.subscription_id, True)]
    assert len(uow.subscription_runtime.added) == 1
    assert len(uow.subscription_quota_cycles.added) == 1
    cycle = result.quota_cycles[0]
    assert cycle.metric_code == QUOTA_METRIC_CODE
    assert cycle.customer_ref == "customer-1"
    assert cycle.plan_code == projection.plan_code
    assert cycle.plan_catalog_version == PLAN_FULFILLMENT_CATALOG_VERSION
    assert tuple(cycle.entitlement_codes) == projection.entitlement_codes
    assert cycle.quota_profile_ref == projection.quota_profile_ref
    assert cycle.base_limit_units == projection.monthly_unit_allowance
    assert cycle.used_units == 0
    assert cycle.top_up_units == 0
    assert cycle.rollover_units == 0


@pytest.mark.asyncio
async def test_bootstrap_in_unit_defers_commit_to_outer_transaction() -> None:
    uow = Uow()
    source = _source()

    result = await bootstrap_subscription_runtime_in_unit(
        source=source,
        quota_profile=_profile(),
        uow=uow,
    )

    assert result.replayed is False
    assert uow.commit_count == 0
    assert len(uow.subscription_runtime.added) == 1
    assert len(uow.subscription_quota_cycles.added) == 1


@pytest.mark.asyncio
async def test_bootstrap_replay_is_read_only_and_requires_exact_cycle_binding() -> None:
    source = _source()
    projection = _projection()
    profile = _profile()
    uow = Uow()
    runtime = SimpleNamespace(
        subscription_id=source.subscription_id,
        customer_ref="customer-1",
        entitlement_profile_ref=projection.entitlement_profile_ref,
        quota_profile_ref=projection.quota_profile_ref,
        access_stage="active",
    )
    cycle = SimpleNamespace(
        subscription_id=source.subscription_id,
        customer_ref="customer-1",
        plan_code=projection.plan_code,
        plan_catalog_version=PLAN_FULFILLMENT_CATALOG_VERSION,
        entitlement_codes=list(projection.entitlement_codes),
        quota_profile_ref=projection.quota_profile_ref,
        metric_code=QUOTA_METRIC_CODE,
        base_limit_units=projection.monthly_unit_allowance,
    )
    uow.subscription_runtime.existing = runtime
    uow.subscription_quota_cycles.current = cycle
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)

    result = await service(source=source, quota_profile=profile)

    assert result.replayed is True
    assert result.quota_cycles == (cycle,)
    assert uow.commit_count == 0
    assert uow.subscription_runtime.added == []
    assert uow.subscription_quota_cycles.added == []
    assert uow.subscription_quota_cycles.calls[-1][-1] is True

    cycle.base_limit_units += 1
    with pytest.raises(SubscriptionRuntimeError, match="conflicts"):
        await service(source=source, quota_profile=profile)
    assert uow.commit_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,profile",
    (
        (_source(subscription_status="suspended"), _profile()),
        (_source(quota_profile_ref="other-profile"), _profile()),
        (_source(effective_at=datetime(2026, 8, 5)), _profile()),
        (
            _source(),
            SubscriptionQuotaProfile(
                profile_ref=_projection().quota_profile_ref,
                period_days=30,
                metrics=(SubscriptionQuotaMetric("api_calls", 10_000),),
            ),
        ),
    ),
)
async def test_bootstrap_invalid_or_non_authoritative_sources_fail_closed(
    source,
    profile,
) -> None:
    uow = Uow()
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(source=source, quota_profile=profile)

    assert uow.commit_count == 0
    assert uow.subscription_runtime.added == []
    assert uow.subscription_quota_cycles.added == []


@pytest.mark.asyncio
async def test_bootstrap_cross_customer_replay_fails_without_mutation() -> None:
    source = _source()
    uow = Uow()
    uow.subscription_runtime.existing = SimpleNamespace(
        customer_ref="customer-2",
        entitlement_profile_ref=source.entitlement_profile_ref,
        quota_profile_ref=source.quota_profile_ref,
        access_stage="active",
    )
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(source=source, quota_profile=_profile())

    assert uow.commit_count == 0
    assert uow.subscription_runtime.added == []
    assert uow.subscription_quota_cycles.added == []
