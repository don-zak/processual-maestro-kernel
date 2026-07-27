from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MIGRATION = ROOT / "alembic" / "versions" / "20260727_0011_admin_marketplace_persistence.py"

ALEMBIC_INI = ROOT / "alembic.ini"

EXPECTED_TABLES = {
    "admin_market_plans",
    "admin_market_offers",
    "admin_market_subscriptions",
    "admin_market_trials",
    "admin_market_orders",
    "admin_market_payment_verifications",
    "admin_market_invoices",
    "admin_market_entitlement_activations",
    "admin_market_channel_eligibilities",
    "admin_market_channel_selections",
    "admin_market_commercial_decisions",
    "admin_market_audit_records",
}


def _alembic_environment() -> dict[str, str]:
    environment = os.environ.copy()

    environment.setdefault(
        "DATABASE_URL",
        ("postgresql+asyncpg://user:password@localhost:5432/maestro"),
    )

    return environment


def _offline(*arguments: str) -> str:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            *arguments,
        ],
        cwd=ROOT,
        env=_alembic_environment(),
        check=True,
        capture_output=True,
        text=True,
    )

    return completed.stdout.lower()


def test_migration_metadata_is_linear_and_exact() -> None:
    namespace: dict[str, object] = {}

    exec(
        compile(
            MIGRATION.read_text(encoding="utf-8"),
            MIGRATION,
            "exec",
        ),
        namespace,
    )

    assert namespace["revision"] == "20260727_0011"
    assert namespace["down_revision"] == "20260723_0010"
    assert namespace["branch_labels"] is None
    assert namespace["depends_on"] is None


def test_offline_upgrade_creates_exact_table_catalog() -> None:
    sql = _offline(
        "upgrade",
        "20260727_0011",
        "--sql",
    )

    for table_name in EXPECTED_TABLES:
        assert f"create table {table_name}" in sql


def test_offline_upgrade_preserves_commercial_constraints() -> None:
    sql = _offline(
        "upgrade",
        "20260727_0011",
        "--sql",
    )

    required = (
        "amount >= 0",
        "maestro_direct",
        "lemon_squeezy",
        "customer_choice_allowed",
        "admin_review_required",
        "automatic_activation_allowed",
        "platform_authority = 'platform_admin'",
        "awaiting_payment_verification",
        "subscription_activation_decided",
        "on delete restrict",
        "on delete cascade",
    )

    for marker in required:
        assert marker in sql


def test_offline_upgrade_creates_required_indexes() -> None:
    sql = _offline(
        "upgrade",
        "20260727_0011",
        "--sql",
    )

    expected_indexes = (
        "ix_admin_market_offers_plan_status",
        "ix_admin_market_subscriptions_customer_status",
        "ix_admin_market_trials_customer_status",
        "ix_admin_market_orders_customer_status",
        "ix_admin_market_payment_verifications_order_status",
        "ix_admin_market_invoices_order",
        "ix_admin_market_entitlement_subscription",
        "ix_admin_market_channel_selections_customer",
        "ix_admin_market_decisions_resource",
        "ix_admin_market_audit_resource_time",
        "ix_admin_market_audit_correlation",
    )

    for index_name in expected_indexes:
        assert index_name in sql


def test_offline_downgrade_removes_exact_table_catalog() -> None:
    sql = _offline(
        "downgrade",
        "20260727_0011:20260723_0010",
        "--sql",
    )

    for table_name in EXPECTED_TABLES:
        assert f"drop table {table_name}" in sql


def test_migration_contains_no_runtime_or_secret_operations() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()

    forbidden_runtime = (
        "requests.",
        "httpx.",
        "socket.",
        "subprocess.",
        "redis.",
        "create_async_engine",
        "asyncsession",
        "processual_api.admin_marketplace.models",
    )

    for marker in forbidden_runtime:
        assert marker not in source

    forbidden_columns = (
        '"password"',
        '"raw_secret"',
        '"payment_evidence"',
        '"card_number"',
        '"cvv"',
        '"access_token"',
        '"refresh_token"',
        '"webhook_signature"',
    )

    for marker in forbidden_columns:
        assert marker not in source
