from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"


def test_offer_provenance_revision_renders_offline_sql() -> None:
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
            "20260809_0046:20260817_0047",
            "--sql",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "commercial offer provenance offline migration failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    lowered = result.stdout.lower()
    assert "admin_market_offer_provenance" in lowered
    assert "offer_id" in lowered
    assert "evidence_sha256" in lowered
    assert "source_pricing_version" in lowered
    assert "source_pricebook_version" in lowered
