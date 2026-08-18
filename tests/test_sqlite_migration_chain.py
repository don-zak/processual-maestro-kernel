from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


HEAD_REVISION = "20260818_0050"
PREVIOUS_REVISION = "20260818_0049"
PARTIAL_DEFAULT_INDEX = "uq_admin_market_payment_destinations_active_default"


def _run_alembic(
    repo_root: Path,
    database_url: str,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return result


def _assert_current_head(repo_root: Path, database_url: str) -> None:
    result = _run_alembic(repo_root, database_url, "current")
    combined = f"{result.stdout}\n{result.stderr}"
    assert HEAD_REVISION in combined, combined


def _assert_partial_default_index(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (PARTIAL_DEFAULT_INDEX,),
        ).fetchone()

    assert row is not None, f"missing SQLite index {PARTIAL_DEFAULT_INDEX}"
    index_sql = (row[0] or "").lower()
    normalized = " ".join(index_sql.split())
    assert " where " in normalized, index_sql
    assert "is_active = 1" in normalized, index_sql
    assert "is_default = 1" in normalized, index_sql


def test_fresh_sqlite_upgrade_downgrade_reupgrade(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migration-chain.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    _run_alembic(repo_root, database_url, "upgrade", "head")
    _assert_current_head(repo_root, database_url)
    _assert_partial_default_index(database_path)

    _run_alembic(repo_root, database_url, "downgrade", "-1")
    downgraded = _run_alembic(repo_root, database_url, "current")
    assert PREVIOUS_REVISION in f"{downgraded.stdout}\n{downgraded.stderr}"

    _run_alembic(repo_root, database_url, "upgrade", "head")
    _assert_current_head(repo_root, database_url)
    _assert_partial_default_index(database_path)
