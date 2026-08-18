from __future__ import annotations

from pathlib import Path

from processual_api.admin_marketplace.models import (
    AdminMarketOffer,
    AdminMarketSubscription,
    AdminMarketTrial,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_SNAPSHOT_MIGRATION = (
    ROOT / "alembic" / "versions" / "20260806_0038_authoritative_plan_snapshot.py"
)


def _plan_foreign_key(model: type) -> object:
    foreign_keys = list(model.__table__.c.plan_id.foreign_keys)
    assert len(foreign_keys) == 1
    return foreign_keys[0]


def test_plan_history_references_are_restrictive_not_cascading() -> None:
    for model in (AdminMarketOffer, AdminMarketSubscription, AdminMarketTrial):
        foreign_key = _plan_foreign_key(model)
        assert foreign_key.target_fullname == "admin_market_plans.id"
        assert foreign_key.ondelete == "RESTRICT"


def test_authoritative_quota_snapshot_preserves_historical_plan_identity() -> None:
    source = PLAN_SNAPSHOT_MIGRATION.read_text(encoding="utf-8")

    assert 'TABLE = "admin_market_subscription_quota_cycles"' in source
    assert 'batch.add_column(sa.Column("plan_code", sa.String(128)))' in source
    assert 'batch.add_column(sa.Column("plan_catalog_version", sa.String(64)))' in source
    assert "JOIN admin_market_plans p ON p.id = s.plan_id" in source
    assert "WHERE s.id = {TABLE}.subscription_id" in source
    assert "Authoritative plan snapshot migration found orphaned quota cycles" in source
