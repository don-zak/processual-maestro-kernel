from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_alembic(repo_root: Path, database_url: str, *args: str) -> None:
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


def test_fresh_sqlite_upgrade_downgrade_reupgrade(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migration-chain.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    _run_alembic(repo_root, database_url, "upgrade", "head")
    _run_alembic(repo_root, database_url, "current")
    _run_alembic(repo_root, database_url, "downgrade", "-1")
    _run_alembic(repo_root, database_url, "upgrade", "head")
    _run_alembic(repo_root, database_url, "current")
