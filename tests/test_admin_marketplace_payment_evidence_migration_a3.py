from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260805_0022_payment_evidence_verification.py"


def offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+asyncpg://localhost/maestro"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.lower()


def test_payment_evidence_revision_extends_contract_head() -> None:
    namespace: dict[str, object] = {}
    exec(compile(MIGRATION.read_text(encoding="utf-8"), str(MIGRATION), "exec"), namespace)

    assert namespace["revision"] == "20260805_0022"
    assert namespace["down_revision"] == "20260805_0021"


def test_payment_evidence_upgrade_has_safe_matching_and_verification_constraints() -> None:
    sql = offline("upgrade", "20260805_0021:20260805_0022", "--sql")

    assert "create table admin_market_payment_evidence" in sql
    assert "safe_source_reference" in sql
    assert "source_reference_hash" in sql
    assert "submission_idempotency_key_hash" in sql
    assert "reference_matched" in sql
    assert "payment_evidence_recorded" in sql
    assert "add constraint uq_admin_market_payment_verifications_order_id unique" in sql
    assert "raw_reference" not in sql
    assert "attachment" not in sql


def test_payment_evidence_downgrade_is_data_guarded() -> None:
    sql = offline("downgrade", "20260805_0022:20260805_0021", "--sql")

    assert "downgrade blocked: payment evidence or verification exists" in sql
    assert "drop table admin_market_payment_evidence" in sql
