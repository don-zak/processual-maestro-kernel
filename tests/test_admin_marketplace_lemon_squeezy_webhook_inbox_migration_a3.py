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
    / "20260805_0026_lemon_squeezy_webhook_inbox.py"
)


def offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        "postgresql+asyncpg://offline:offline@localhost:5432/maestro"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, (
        f"alembic {' '.join(arguments)} failed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return completed.stdout.lower()


def test_webhook_inbox_revision_extends_notification_outbox_head() -> None:
    namespace: dict[str, object] = {}
    source = MIGRATION.read_text(encoding="utf-8")
    exec(compile(source, str(MIGRATION), "exec"), namespace)

    assert namespace["revision"] == "20260805_0026"
    assert namespace["down_revision"] == "20260805_0025"


def test_webhook_inbox_upgrade_is_idempotent_and_cross_account_bound() -> None:
    sql = offline("upgrade", "20260805_0025:20260805_0026", "--sql")

    assert "create table admin_market_lemon_squeezy_webhook_inbox" in sql
    assert "event_identity_hash" in sql
    assert "payload_digest" in sql
    assert "processing_status" in sql
    assert "attempt_count >= 0" in sql
    assert "uq_admin_market_ls_webhook_event_identity" in sql
    assert "uq_admin_market_ls_webhook_payload_digest" in sql
    assert "uq_admin_market_ls_webhook_resource_binding" in sql
    for marker in (
        "store_id",
        "event_name",
        "resource_type",
        "external_resource_id",
        "customer_ref",
        "order_ref",
        "offer_ref",
    ):
        assert marker in sql


def test_webhook_inbox_downgrade_is_guarded_and_offline_safe() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    sql = offline("downgrade", "20260805_0026:20260805_0025", "--sql")

    assert "Downgrade blocked: Lemon Squeezy webhook inbox rows exist" in source
    assert "context.is_offline_mode()" in source
    assert "drop table admin_market_lemon_squeezy_webhook_inbox" in sql
