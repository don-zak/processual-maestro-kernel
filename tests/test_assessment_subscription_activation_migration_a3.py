from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVISION = "20260809_0045"
PREVIOUS_REVISION = "20260809_0044"


def _run(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def test_assessment_subscription_activation_migration_allows_offerless_binding(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "assessment-subscription.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    # This test owns the 0045 contract specifically. Newer head migrations have
    # their own tests and must not change the expected downgrade target here.
    _run(database_url, "upgrade", REVISION)

    with sqlite3.connect(database_path) as connection:
        current = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        assert current == (REVISION,)

        subscription_columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(admin_market_subscriptions)")
        }
        assert subscription_columns["offer_id"][3] == 0

        binding_columns = {
            row[1]: row
            for row in connection.execute(
                "PRAGMA table_info(admin_market_assessment_subscription_bindings)"
            )
        }
        assert {
            "subscription_id",
            "assessment_binding_hash",
            "assessment_id",
            "customer_ref",
            "public_plan_id",
            "entitlement_source_plan_code",
            "entitlement_plan_id",
            "entitlement_profile_ref",
            "quota_profile_ref",
            "activation_idempotency_key_hash",
        }.issubset(binding_columns)

        indexes = {
            row[1]
            for row in connection.execute(
                "PRAGMA index_list(admin_market_assessment_subscription_bindings)"
            )
        }
        assert "ix_assessment_subscription_binding_customer" in indexes

    _run(database_url, "downgrade", "-1")
    current = _run(database_url, "current")
    assert PREVIOUS_REVISION in f"{current.stdout}\n{current.stderr}"

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name = 'admin_market_assessment_subscription_bindings'"
        ).fetchone()
        assert table is None
        subscription_columns = {
            row[1]: row for row in connection.execute("PRAGMA table_info(admin_market_subscriptions)")
        }
        assert subscription_columns["offer_id"][3] == 1
