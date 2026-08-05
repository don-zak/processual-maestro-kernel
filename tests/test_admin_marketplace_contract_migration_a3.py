from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260805_0021_contract_completion.py"


def offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql://user:pass@localhost/maestro"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_contract_migration_is_next_single_revision() -> None:
    namespace: dict[str, object] = {}
    exec(compile(MIGRATION.read_text(encoding="utf-8"), MIGRATION, "exec"), namespace)

    assert namespace["revision"] == "20260805_0021"
    assert namespace["down_revision"] == "20260804_0020"


def test_upgrade_sql_creates_immutable_contract_and_audit_contract() -> None:
    sql = offline("upgrade", "20260804_0020:20260805_0021", "--sql")

    assert "CREATE TABLE admin_market_contracts" in sql
    assert "completion_idempotency_key_hash" in sql
    assert "evidence_reference" in sql
    assert "authenticated_clickwrap" in sql
    assert "contract_completed" in sql


def test_downgrade_blocks_completed_contract_data_loss() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    sql = offline("downgrade", "20260805_0021:20260804_0020", "--sql")

    assert "Downgrade blocked: completed commercial contract exists" in source
    assert "DROP TABLE admin_market_contracts" in sql
