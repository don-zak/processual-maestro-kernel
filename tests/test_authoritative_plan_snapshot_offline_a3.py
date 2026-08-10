from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"


def test_authoritative_plan_snapshot_revision_renders_offline_sql() -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+asyncpg://localhost/maestro"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            "upgrade",
            "20260806_0037:20260806_0038",
            "--sql",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "authoritative plan snapshot offline migration failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    lowered = result.stdout.lower()
    assert "admin_market_subscription_quota_cycles" in lowered
    assert "plan_code" in lowered
    assert "plan_catalog_version" in lowered
    assert "entitlement_codes" in lowered
