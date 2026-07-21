from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260722_0002_identity_terms_acceptance.py"


def _offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+asyncpg://localhost/maestro"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.lower()


def test_terms_revision_is_chained_and_reversible() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260722_0002"' in source
    assert 'down_revision: str | None = "20260721_0001"' in source
    assert 'op.create_table( "identity_terms_acceptances",' in " ".join(source.split())
    assert 'op.drop_table("identity_terms_acceptances")' in source
    assert "uq_identity_terms_acceptance_user_version" in source


def test_offline_head_contains_terms_acceptance_and_downgrade_removes_it() -> None:
    upgrade_sql = _offline("upgrade", "head", "--sql")
    downgrade_sql = _offline("downgrade", "20260722_0002:20260721_0001", "--sql")
    assert "create table identity_terms_acceptances" in upgrade_sql
    assert "drop table identity_terms_acceptances" in downgrade_sql
