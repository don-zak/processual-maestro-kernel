from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_quota_profiles import (
    SubscriptionQuotaMetric,
    SubscriptionQuotaProfile,
    build_quota_profile_catalog,
    validate_quota_profile,
)
from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError
from processual_api.admin_marketplace.subscription_runtime_bootstrap import (
    SubscriptionRuntimeBootstrapInput,
    bootstrap_subscription_runtime_factory,
    bootstrap_subscription_runtime_in_unit,
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


class QuotaRepository:
    def __init__(self) -> None:
        self.current = {}
        self.added = []
        self.calls = []

    async def get_current(self, *, subscription_id, metric_code, occurred_at, for_update=False):
        self.calls.append((subscription_id, metric_code, occurred_at, for_update))
        return self.current.get(metric_code)

    def add(self, value):
        self.added.append(value)


class Uow:
    def __init__(self) -> None:
        self.subscription_runtime = RuntimeRepository()
        self.subscription_quotas = QuotaRepository()
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def commit(self):
        self.commit_count += 1


def _profile() -> SubscriptionQuotaProfile:
    return SubscriptionQuotaProfile(
        profile_ref="professional-v1",
        period_days=30,
        metrics=(
            SubscriptionQuotaMetric("api_calls", 1000),
            SubscriptionQuotaMetric("workflow_runs", 100),
        ),
    )


def _source(**overrides):
    values = dict(
        subscription_id=uuid.uuid4(),
        customer_ref="customer-1",
        entitlement_profile_ref="professional-entitlements-v1",
        quota_profile_ref="professional-v1",
        subscription_status="active",
        effective_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return SubscriptionRuntimeBootstrapInput(**values)


def test_quota_profiles_are_normalized_and_reject_duplicates_or_invalid_limits() -> None:
    normalized = validate_quota_profile(
        SubscriptionQuotaProfile(
            profile_ref=" Professional-V1 ",
            period_days=30,
            metrics=(SubscriptionQuotaMetric(" API_CALLS ", 10),),
        )
    )
    assert normalized.profile_ref == "professional-v1"
    assert normalized.metrics[0].metric_code == "api_calls"

    with pytest.raises(SubscriptionRuntimeError):
        validate_quota_profile(
            SubscriptionQuotaProfile(
                profile_ref="p",
                period_days=30,
                metrics=(
                    SubscriptionQuotaMetric("api_calls", 1),
                    SubscriptionQuotaMetric(" API_CALLS ", 2),
                ),
            )
        )
    with pytest.raises(SubscriptionRuntimeError):
        validate_quota_profile(
            SubscriptionQuotaProfile(
                profile_ref="p",
                period_days=0,
                metrics=(SubscriptionQuotaMetric("api_calls", 1),),
            )
        )
    with pytest.raises(SubscriptionRuntimeError):
        build_quota_profile_catalog((_profile(), _profile()))


@pytest.mark.asyncio
async def test_bootstrap_creates_runtime_and_all_quota_accounts_with_one_commit() -> None:
    uow = Uow()
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)
    source = _source()

    result = await service(source=source, quota_profile=_profile())

    assert result.replayed is False
    assert uow.commit_count == 1
    assert uow.subscription_runtime.calls == [(source.subscription_id, True)]
    assert len(uow.subscription_runtime.added) == 1
    assert len(uow.subscription_quotas.added) == 2
    assert {item.metric_code for item in result.quota_accounts} == {
        "api_calls",
        "workflow_runs",
    }
    assert all(item.customer_ref == "customer-1" for item in result.quota_accounts)
    assert all(item.used_units == 0 for item in result.quota_accounts)


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
    assert len(uow.subscription_quotas.added) == 2


@pytest.mark.asyncio
async def test_bootstrap_replay_is_read_only_and_requires_complete_exact_quota_binding() -> None:
    source = _source()
    uow = Uow()
    uow.subscription_runtime.existing = SimpleNamespace(
        subscription_id=source.subscription_id,
        customer_ref="customer-1",
        entitlement_profile_ref="professional-entitlements-v1",
        quota_profile_ref="professional-v1",
        access_stage="active",
    )
    for metric, limit in (("api_calls", 1000), ("workflow_runs", 100)):
        uow.subscription_quotas.current[metric] = SimpleNamespace(
            customer_ref="customer-1",
            quota_profile_ref="professional-v1",
            limit_units=limit,
        )
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)

    result = await service(source=source, quota_profile=_profile())

    assert result.replayed is True
    assert uow.commit_count == 0
    assert uow.subscription_runtime.added == []
    assert uow.subscription_quotas.added == []
    assert all(call[-1] is True for call in uow.subscription_quotas.calls)

    del uow.subscription_quotas.current["workflow_runs"]
    with pytest.raises(SubscriptionRuntimeError):
        await service(source=source, quota_profile=_profile())
    assert uow.commit_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    (
        _source(subscription_status="suspended"),
        _source(quota_profile_ref="other-profile"),
        _source(effective_at=datetime(2026, 8, 5)),
    ),
)
async def test_bootstrap_invalid_sources_fail_before_opening_or_committing(source) -> None:
    uow = Uow()
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(source=source, quota_profile=_profile())

    assert uow.subscription_runtime.calls == []
    assert uow.commit_count == 0


@pytest.mark.asyncio
async def test_bootstrap_cross_customer_replay_fails_without_mutation() -> None:
    source = _source()
    uow = Uow()
    uow.subscription_runtime.existing = SimpleNamespace(
        customer_ref="customer-2",
        entitlement_profile_ref="professional-entitlements-v1",
        quota_profile_ref="professional-v1",
        access_stage="active",
    )
    service = bootstrap_subscription_runtime_factory(uow_factory=lambda: uow)

    with pytest.raises(SubscriptionRuntimeError):
        await service(source=source, quota_profile=_profile())

    assert uow.commit_count == 0
    assert uow.subscription_runtime.added == []
    assert uow.subscription_quotas.added == []
