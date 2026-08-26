from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "alembic"
    / "versions"
    / "20260805_0028_subscription_runtime_quotas_usage.py"
)
RETIREMENT_MIGRATION_PATH = (
    ROOT
    / "alembic"
    / "versions"
    / "20260822_0060_retire_legacy_subscription_quota.py"
)
RUNTIME_PERSISTENCE_PATH = (
    ROOT
    / "processual_api"
    / "admin_marketplace"
    / "subscription_runtime_persistence.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "migration_20260805_0028_subscription_runtime_quotas_usage",
        MIGRATION_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subscription_runtime_revision_extends_reconciliation_head() -> None:
    migration = _load_migration()
    assert migration.revision == "20260805_0028"
    assert migration.down_revision == "20260805_0027"


def test_subscription_runtime_migration_contains_security_constraints() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    required = (
        "used_units <= limit_units",
        "units > 0",
        "idempotency_key_hash",
        "dimensions_digest",
        "uq_admin_market_subscription_usage_idempotency",
        "uq_admin_market_subscription_quota_period",
        "access_stage IN ('active','grace','suspended','terminated')",
        "ondelete=\"RESTRICT\"",
        "context.is_offline_mode()",
        "Downgrade blocked: subscription runtime, quota, or usage rows exist",
    )
    for marker in required:
        assert marker in source


def test_legacy_usage_repository_is_retired_by_revision_0060() -> None:
    runtime_source = RUNTIME_PERSISTENCE_PATH.read_text(encoding="utf-8")
    retirement_source = RETIREMENT_MIGRATION_PATH.read_text(encoding="utf-8")

    assert "SqlAlchemySubscriptionUsageRepository" not in runtime_source
    assert "SqlAlchemySubscriptionQuotaRepository" not in runtime_source
    assert "AdminMarketSubscriptionUsageLedger" not in runtime_source
    assert "AdminMarketSubscriptionQuotaAccount" not in runtime_source
    assert 'revision: str = "20260822_0060"' in retirement_source
    assert 'LEGACY_USAGE = "admin_market_subscription_usage_ledger"' in retirement_source
    assert 'LEGACY_QUOTAS = "admin_market_subscription_quota_accounts"' in retirement_source
    assert "_backfill_and_verify()" in retirement_source
    assert "op.drop_table(LEGACY_USAGE)" in retirement_source
    assert "op.drop_table(LEGACY_QUOTAS)" in retirement_source
