from __future__ import annotations

import importlib


def test_subscription_runtime_revision_extends_reconciliation_head() -> None:
    migration = importlib.import_module(
        "alembic.versions.20260805_0028_subscription_runtime_quotas_usage"
    )
    assert migration.revision == "20260805_0028"
    assert migration.down_revision == "20260805_0027"


def test_subscription_runtime_migration_contains_security_constraints() -> None:
    migration = importlib.import_module(
        "alembic.versions.20260805_0028_subscription_runtime_quotas_usage"
    )
    source = __import__("inspect").getsource(migration)

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


def test_usage_ledger_has_no_update_or_delete_contract() -> None:
    from processual_api.admin_marketplace.subscription_runtime_persistence import (
        SqlAlchemySubscriptionUsageRepository,
    )

    public_methods = {
        name
        for name, value in vars(SqlAlchemySubscriptionUsageRepository).items()
        if callable(value) and not name.startswith("_")
    }
    assert public_methods == {"get_by_idempotency_hash", "add"}
