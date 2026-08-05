from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260805_0023_subscription_activation.py"


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


def test_subscription_activation_revision_extends_payment_head() -> None:
    namespace: dict[str, object] = {}
    source = MIGRATION.read_text(encoding="utf-8")
    exec(compile(source, str(MIGRATION), "exec"), namespace)

    assert namespace["revision"] == "20260805_0023"
    assert namespace["down_revision"] == "20260805_0022"


def test_subscription_activation_upgrade_enforces_single_activation() -> None:
    sql = offline("upgrade", "20260805_0022:20260805_0023", "--sql")

    assert "fk_admin_market_subscription_order" in sql
    assert "uq_admin_market_subscriptions_order_id" in sql
    assert "uq_admin_market_subscriptions_active_customer" in sql
    assert "where status = 'active'" in sql
    assert "uq_admin_market_entitlement_activations_order_id" in sql
    assert "uq_admin_market_entitlement_activations_idem_hash" in sql
    assert "activation_idempotency_key_hash" in sql


def test_subscription_activation_downgrade_is_data_guarded() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()
    sql = offline("downgrade", "20260805_0023:20260805_0022", "--sql")

    assert "downgrade blocked: automatic subscription activation exists" in source
    assert "drop column order_id" in sql
