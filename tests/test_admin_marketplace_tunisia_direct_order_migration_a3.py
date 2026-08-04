from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "alembic/versions/20260804_0020_tunisia_direct_order_foundation.py"
)


def offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql://user:pass@localhost/maestro"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_migration_revision_and_chain_are_explicit() -> None:
    namespace: dict[str, object] = {}
    source = MIGRATION.read_text(encoding="utf-8")
    exec(compile(source, MIGRATION, "exec"), namespace)

    assert namespace["revision"] == "20260804_0020"
    assert namespace["down_revision"] == "20260804_0019"


def test_upgrade_sql_adds_confirmed_address_and_safe_direct_order_contract() -> None:
    sql = offline("upgrade", "20260804_0019:20260804_0020", "--sql")

    assert "address_status" in sql
    assert "address_source" in sql
    assert "address_verified_at" in sql
    assert "creation_idempotency_key_hash" in sql
    assert "payment_destination_snapshot" in sql
    assert "order_created" in sql
    assert "identity_customer" in sql
    assert "selected_channel != 'maestro_direct' OR currency = 'TND'" in sql
    assert "selected_channel != 'maestro_direct' OR country_code = 'TN'" in sql


def test_downgrade_sql_blocks_loss_of_customer_order_audit() -> None:
    sql = offline("downgrade", "20260804_0020:20260804_0019", "--sql")

    assert "Downgrade blocked: customer direct-order audit exists" in sql
    assert "DROP COLUMN payment_destination_snapshot" in sql
