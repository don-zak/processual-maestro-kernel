from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "alembic"
    / "versions"
    / "20260804_0019_payment_destination_idempotency.py"
)


def _offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        "postgresql+asyncpg://user:password@localhost:5432/maestro"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.lower()


def test_idempotency_migration_is_linear() -> None:
    namespace: dict[str, object] = {}
    exec(
        compile(MIGRATION.read_text(encoding="utf-8"), MIGRATION, "exec"),
        namespace,
    )

    assert namespace["revision"] == "20260804_0019"
    assert namespace["down_revision"] == "20260804_0018"


def test_idempotency_migration_adds_hash_only() -> None:
    sql = _offline("upgrade", "20260804_0018:20260804_0019", "--sql")

    assert "creation_idempotency_key_hash" in sql
    assert (
        "add constraint uq_admin_market_payment_destinations_create_idem_hash"
    ) in sql
    assert "unique (creation_idempotency_key_hash)" in sql
    assert "raw_idempotency" not in sql
    assert "idempotency_key varchar" not in sql


def test_idempotency_migration_downgrade_removes_column() -> None:
    sql = _offline("downgrade", "20260804_0019:20260804_0018", "--sql")

    assert "drop column creation_idempotency_key_hash" in sql
