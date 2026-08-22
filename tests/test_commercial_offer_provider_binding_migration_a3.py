from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"


def test_offer_provider_binding_revision_renders_offline_sql() -> None:
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
            "20260817_0047:20260817_0048",
            "--sql",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "commercial offer provider binding offline migration failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    lowered = result.stdout.lower()
    assert "admin_market_offer_provider_bindings" in lowered
    assert "provider_variant_id" in lowered
    assert "verification_reference" in lowered
    assert "verified_at" in lowered
