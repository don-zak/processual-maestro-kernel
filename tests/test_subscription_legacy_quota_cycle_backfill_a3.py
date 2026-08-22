from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.subscription_legacy_quota_cycle_backfill import (
    backfill_legacy_quota_cycles_in_session,
)
from processual_api.admin_marketplace.subscription_quota_rollover_persistence import (
    AdminMarketSubscriptionQuotaCycle,
)
from processual_api.admin_marketplace.subscription_quota_usage_persistence import (
    AdminMarketSubscriptionQuotaCycleUsage,
)
from processual_api.admin_marketplace.subscription_runtime import SubscriptionRuntimeError


class _ScalarRows:
    def __init__(self, values):
        self._values = tuple(values)

    def all(self):
        return self._values


class _FakeSession:
    def __init__(self, *, scalar_values, scalar_rows):
        self._scalar_values = list(scalar_values)
        self._scalar_rows = [tuple(values) for values in scalar_rows]
        self.added = []
        self.flush_count = 0
        self.commit_count = 0

    async def scalar(self, statement):
        del statement
        return self._scalar_values.pop(0)

    async def scalars(self, statement):
        del statement
        return _ScalarRows(self._scalar_rows.pop(0))

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1

    async def commit(self):
        self.commit_count += 1


def _fixtures(*, limit_units=125_000, used_units=25_000):
    started = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    ended = datetime(2026, 9, 9, 20, 0, tzinfo=UTC)
    subscription_id = uuid.UUID("10000000-0000-0000-0000-000000000001")
    plan_id = uuid.UUID("10000000-0000-0000-0000-000000000002")
    account_id = uuid.UUID("10000000-0000-0000-0000-000000000003")
    profile_ref = "assessment_quota_test"
    subscription = SimpleNamespace(
        id=subscription_id,
        customer_ref="institution-acme",
        plan_id=plan_id,
        status="active",
    )
    plan = SimpleNamespace(
        id=plan_id,
        plan_code="academic",
        quota_profile_ref="academic-default-5k",
    )
    binding = SimpleNamespace(
        subscription_id=subscription_id,
        customer_ref="institution-acme",
        entitlement_plan_id=plan_id,
        entitlement_source_plan_code="academic",
        quota_profile_ref=profile_ref,
    )
    profile = SimpleNamespace(
        profile_ref=profile_ref,
        customer_ref="institution-acme",
        definition_version="2026-08-assessment-quota-profile-v1",
        entitlement_codes_json=["maestro_execution", "academic_use"],
        metric_code="maestro_units",
        limit_units=limit_units,
    )
    account = SimpleNamespace(
        id=account_id,
        subscription_id=subscription_id,
        customer_ref="institution-acme",
        quota_profile_ref=profile_ref,
        metric_code="maestro_units",
        period_start=started,
        period_end=ended,
        limit_units=limit_units,
        used_units=used_units,
        version=3,
    )
    usage = SimpleNamespace(
        id=uuid.UUID("10000000-0000-0000-0000-000000000004"),
        quota_account_id=account_id,
        subscription_id=subscription_id,
        customer_ref="institution-acme",
        metric_code="maestro_units",
        units=25_000,
        idempotency_key_hash="a" * 64,
        dimensions_digest="b" * 64,
        occurred_at=datetime(2026, 8, 10, 20, 0, tzinfo=UTC),
        recorded_at=datetime(2026, 8, 10, 20, 0, tzinfo=UTC),
    )
    return subscription, plan, binding, profile, account, usage


@pytest.mark.asyncio
async def test_backfill_preserves_assessment_quota_and_usage_replay_history() -> None:
    subscription, plan, binding, profile, account, usage = _fixtures()
    session = _FakeSession(
        scalar_values=[
            subscription,
            plan,
            binding,
            profile,
            None,
            None,
        ],
        scalar_rows=[(account,), (usage,)],
    )

    result = await backfill_legacy_quota_cycles_in_session(session=session)

    assert result.scanned_accounts == 1
    assert result.created_cycles == 1
    assert result.scanned_usage == 1
    assert result.created_usage == 1
    assert session.flush_count == 1
    assert session.commit_count == 1

    cycle = next(
        value
        for value in session.added
        if isinstance(value, AdminMarketSubscriptionQuotaCycle)
    )
    migrated_usage = next(
        value
        for value in session.added
        if isinstance(value, AdminMarketSubscriptionQuotaCycleUsage)
    )
    assert cycle.subscription_id == subscription.id
    assert cycle.plan_code == "academic"
    assert cycle.plan_catalog_version == profile.definition_version
    assert cycle.quota_profile_ref == profile.profile_ref
    assert cycle.base_limit_units == 125_000
    assert cycle.used_units == 25_000
    assert cycle.period_start == account.period_start
    assert cycle.period_end == account.period_end
    assert migrated_usage.quota_cycle_id == cycle.id
    assert migrated_usage.idempotency_key_hash == usage.idempotency_key_hash
    assert migrated_usage.dimensions_digest == usage.dimensions_digest
    assert migrated_usage.units == usage.units


@pytest.mark.asyncio
async def test_backfill_replays_without_duplicate_cycle_or_usage() -> None:
    subscription, plan, binding, profile, account, usage = _fixtures()
    cycle = AdminMarketSubscriptionQuotaCycle(
        id=uuid.uuid4(),
        subscription_id=subscription.id,
        source_cycle_id=None,
        customer_ref=account.customer_ref,
        plan_code="academic",
        plan_catalog_version=profile.definition_version,
        entitlement_codes=list(profile.entitlement_codes_json),
        quota_profile_ref=profile.profile_ref,
        metric_code="maestro_units",
        period_start=account.period_start,
        period_end=account.period_end,
        base_limit_units=account.limit_units,
        rollover_units=0,
        top_up_units=0,
        rollover_status="available",
        used_units=account.used_units,
        version=account.version,
    )
    migrated_usage = AdminMarketSubscriptionQuotaCycleUsage(
        id=uuid.uuid4(),
        quota_cycle_id=cycle.id,
        subscription_id=usage.subscription_id,
        customer_ref=usage.customer_ref,
        metric_code=usage.metric_code,
        units=usage.units,
        idempotency_key_hash=usage.idempotency_key_hash,
        dimensions_digest=usage.dimensions_digest,
        occurred_at=usage.occurred_at,
        recorded_at=usage.recorded_at,
    )
    session = _FakeSession(
        scalar_values=[
            subscription,
            plan,
            binding,
            profile,
            cycle,
            migrated_usage,
        ],
        scalar_rows=[(account,), (usage,)],
    )

    result = await backfill_legacy_quota_cycles_in_session(session=session)

    assert result.created_cycles == 0
    assert result.created_usage == 0
    assert session.added == []
    assert session.flush_count == 0
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_backfill_fails_closed_on_assessment_quota_drift() -> None:
    subscription, plan, binding, profile, account, usage = _fixtures(
        limit_units=125_000
    )
    account.limit_units = 120_000
    session = _FakeSession(
        scalar_values=[subscription, plan, binding, profile],
        scalar_rows=[(account,)],
    )

    with pytest.raises(SubscriptionRuntimeError, match="conflicts"):
        await backfill_legacy_quota_cycles_in_session(session=session)

    assert session.added == []
    assert session.commit_count == 0
    assert usage.idempotency_key_hash == "a" * 64
