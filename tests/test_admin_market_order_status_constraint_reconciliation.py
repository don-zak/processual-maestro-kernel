from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260828_0047r_repair_admin_market_order_status_constraint.py"


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


def test_revision_rebases_repair_onto_current_release_head() -> None:
    namespace: dict[str, object] = {}
    source = MIGRATION.read_text(encoding="utf-8")
    exec(compile(source, MIGRATION, "exec"), namespace)

    assert namespace["revision"] == "20260828_0047r"
    assert namespace["down_revision"] == "20260809_0046"


def test_upgrade_removes_legacy_overlap_and_keeps_current_status_vocabulary() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    sql = offline("upgrade", "20260809_0046:20260828_0047r", "--sql")

    assert "ck_admin_market_orders_status_allowed" in source
    assert "ck_admin_market_orders_ck_admin_market_orders_status_allowed" in source
    assert "payment_under_review" in sql
    assert "ready_for_activation" in sql
    assert "requires_review" in sql
    assert "DROP CONSTRAINT" in sql
    assert "ADD CONSTRAINT" in sql


def test_downgrade_preserves_guard_against_incompatible_live_statuses() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "WHERE status NOT IN ('draft','cancelled') LIMIT 1" in source
    assert "Downgrade blocked: current order statuses cannot safely restore" in source
    assert "'submitted','awaiting_payment_verification','approved','rejected'" in source
