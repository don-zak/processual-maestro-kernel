from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEAD = "20260901_0049"
PREVIOUS = "20260809_0045"
TABLE = "admin_market_assessment_commercial_terms"


def _run(database_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def test_assessment_commercial_terms_migration_upgrade_and_empty_downgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "assessment-commercial-terms.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    _run(database_url, "upgrade", "head")
    current = _run(database_url, "current")
    assert HEAD in f"{current.stdout}\n{current.stderr}"

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]: row
            for row in connection.execute(f"PRAGMA table_info('{TABLE}')").fetchall()
        }
        assert {
            "terms_ref",
            "assessment_binding_hash",
            "assessment_id",
            "customer_ref",
            "public_plan_id",
            "terms_version",
            "price_source",
            "source_reference",
            "currency",
            "billing_interval",
            "amount_minor_units",
            "approved_by",
            "approval_reference",
            "effective_at",
            "payload_digest",
            "created_at",
        }.issubset(columns)

        indexes = connection.execute(f"PRAGMA index_list('{TABLE}')").fetchall()
        index_names = {row[1] for row in indexes}
        assert "ix_admin_market_assessment_commercial_terms_customer" in index_names
        assert any(row[2] == 1 for row in indexes)

    # Newer migrations are now above the commercial-terms migration. Downgrade
    # explicitly to 0045 so this test still verifies removal of the 0046 table.
    _run(database_url, "downgrade", PREVIOUS)
    current = _run(database_url, "current")
    assert PREVIOUS in f"{current.stdout}\n{current.stderr}"

    with sqlite3.connect(database_path) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE,),
        ).fetchone()
        assert table is None
