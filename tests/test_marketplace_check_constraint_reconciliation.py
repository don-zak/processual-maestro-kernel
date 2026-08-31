from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint

from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)


def _load_reconciliation_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "20260830_0047_reconcile_marketplace_check_constraints.py"
    )
    spec = importlib.util.spec_from_file_location("marketplace_check_reconciliation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reconciliation_targets_only_legacy_order_status_vocabulary() -> None:
    migration = _load_reconciliation_migration()
    legacy = (
        "status IN ('draft','submitted','awaiting_payment_verification','approved',"
        "'rejected','cancelled','fulfilled')"
    )
    current = (
        "status IN ('draft','awaiting_contract','awaiting_payment','payment_under_review',"
        "'ready_for_activation','activated','cancelled','expired','requires_review')"
    )

    assert migration._is_stale_order_status_check(legacy) is True
    assert migration._is_stale_order_status_check(current) is False


def test_reconciliation_targets_superseded_audit_vocabulary_only() -> None:
    migration = _load_reconciliation_migration()

    assert migration._is_stale_audit_check(
        "platform_authority = 'platform_admin'"
    ) is True
    assert migration._is_stale_audit_check(
        "platform_authority IN ('platform_admin','identity_customer','system')"
    ) is False
    assert migration._is_stale_audit_check(
        "action IN ('authority_checked','payment_destination_default_set')"
    ) is True
    assert migration._is_stale_audit_check(
        "action IN ('authority_checked','payment_destination_default_set','order_created')"
    ) is False
    assert migration._is_stale_audit_check(
        "resource_type IN ('sales_channel_eligibility','payment_destination')"
    ) is True
    assert migration._is_stale_audit_check(
        "resource_type IN ('sales_channel_eligibility','payment_destination','contract',"
        "'payment_evidence','payment_reconciliation')"
    ) is False


def test_reconciliation_downgrade_restores_historical_logical_names() -> None:
    migration = _load_reconciliation_migration()

    assert str(
        migration._historical_constraint_name(
            migration.AUDIT_TABLE,
            "ck_admin_market_audit_records_action_allowed",
        )
    ) == (
        "ck_admin_market_audit_records_"
        "ck_admin_market_audit_records_action_allowed"
    )
    assert str(
        migration._historical_constraint_name(
            migration.AUDIT_TABLE,
            "ck_admin_market_audit_records_resource_type_allowed",
        )
    ) == (
        "ck_admin_market_audit_records_"
        "ck_admin_market_audit_records_resource_type_allowed"
    )
    assert str(
        migration._historical_constraint_name(
            migration.ORDER_TABLE,
            "ck_admin_market_orders_status_allowed",
        )
    ) == "ck_admin_market_orders_ck_admin_market_orders_status_allowed"


def test_runtime_metadata_preserves_stage_timestamp_invariants() -> None:
    checks = {
        str(constraint.sqltext)
        for constraint in AdminMarketSubscriptionRuntime.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "(access_stage != 'grace') OR grace_until IS NOT NULL" in checks
    assert "(access_stage != 'suspended') OR suspended_at IS NOT NULL" in checks
    assert "(access_stage != 'terminated') OR terminated_at IS NOT NULL" in checks
