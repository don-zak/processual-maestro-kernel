from __future__ import annotations

from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.commercial_plan_materialization import (
    materialize_commercial_plans_in_session,
)
from processual_api.admin_marketplace.commercial_plan_projection import (
    build_commercial_plan_projections,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_CODE_ALIASES


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class FakeSession:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.added = []
        self.scalar_calls = 0
        self.commit_calls = 0

    async def scalars(self, statement):
        self.scalar_calls += 1
        return FakeScalarResult(self.rows)

    def add(self, row):
        self.added.append(row)
        self.rows.append(row)

    async def commit(self):
        self.commit_calls += 1


def legacy_row(plan_code: str):
    return SimpleNamespace(
        plan_code=plan_code,
        display_name=f"Legacy {plan_code}",
        entitlement_profile_ref=f"legacy:{plan_code}:entitlements",
        quota_profile_ref=f"legacy:{plan_code}:quota",
        metadata_json={"historical": "true"},
    )


@pytest.mark.asyncio
async def test_empty_plan_table_materializes_every_canonical_plan_without_commit() -> None:
    session = FakeSession()

    result = await materialize_commercial_plans_in_session(session)  # type: ignore[arg-type]
    expected_codes = tuple(item.plan_code for item in build_commercial_plan_projections())

    assert result.created == expected_codes
    assert result.updated == ()
    assert result.unchanged == ()
    assert result.isolated_legacy == ()
    assert {row.plan_code for row in session.added} == set(expected_codes)
    assert session.commit_calls == 0


@pytest.mark.asyncio
async def test_materialization_is_idempotent_for_canonical_rows() -> None:
    session = FakeSession()
    first = await materialize_commercial_plans_in_session(session)  # type: ignore[arg-type]
    second = await materialize_commercial_plans_in_session(session)  # type: ignore[arg-type]

    assert first.created
    assert second.created == ()
    assert second.updated == ()
    assert set(second.unchanged) == {item.plan_code for item in build_commercial_plan_projections()}
    assert len(session.added) == len(build_commercial_plan_projections())


@pytest.mark.asyncio
async def test_legacy_plan_rows_are_isolated_not_deleted_or_renamed() -> None:
    old_rows = [legacy_row(code) for code in PLAN_CODE_ALIASES]
    session = FakeSession(old_rows)

    result = await materialize_commercial_plans_in_session(session)  # type: ignore[arg-type]

    assert set(result.isolated_legacy) == set(PLAN_CODE_ALIASES)
    assert {row.plan_code for row in old_rows} == set(PLAN_CODE_ALIASES)
    for row in old_rows:
        assert row.metadata_json["lifecycle_state"] == "legacy_isolated"
        assert row.metadata_json["replacement_plan_code"] == PLAN_CODE_ALIASES[row.plan_code]
        assert row.metadata_json["commercial_authority"] == "compatibility_only"
        assert row.metadata_json["historical"] == "true"


@pytest.mark.asyncio
async def test_legacy_isolation_is_idempotent() -> None:
    row = legacy_row("enterprise")
    session = FakeSession([row])

    first = await materialize_commercial_plans_in_session(session)  # type: ignore[arg-type]
    second = await materialize_commercial_plans_in_session(session)  # type: ignore[arg-type]

    assert first.isolated_legacy == ("enterprise",)
    assert second.isolated_legacy == ()
    assert row.plan_code == "enterprise"
    assert row.metadata_json["replacement_plan_code"] == "enterprise_pilot"
