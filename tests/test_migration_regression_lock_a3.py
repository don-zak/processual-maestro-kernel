from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HEAD_REVISION = "20260817_0048"
PARTIAL_DEFAULT_INDEX = "uq_admin_market_payment_destinations_active_default"
POSTGRES_OFFLINE_URL = (
    "postgresql+asyncpg://offline:offline@localhost:5432/maestro"
)


def _run(
    *arguments: str,
    database_url: str,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if expect_success:
        assert completed.returncode == 0, (
            f"alembic {' '.join(arguments)} failed\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def _assert_head(database_url: str) -> None:
    current = _run("current", database_url=database_url)
    output = f"{current.stdout}\n{current.stderr}"
    assert HEAD_REVISION in output, output


def _assert_partial_default_index(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?",
            (PARTIAL_DEFAULT_INDEX,),
        ).fetchone()

    assert row is not None, f"missing SQLite index {PARTIAL_DEFAULT_INDEX}"
    normalized = " ".join((row[0] or "").lower().split())
    assert " where " in normalized
    assert "is_active = 1" in normalized
    assert "is_default = 1" in normalized


def test_commercial_migrations_render_offline_without_runtime_database_access(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///must-not-be-inherited.db")

    ranges = (
        ("upgrade", "20260804_0019:20260804_0020"),
        ("downgrade", "20260804_0020:20260804_0019"),
        ("upgrade", "20260804_0020:20260805_0021"),
        ("downgrade", "20260805_0021:20260804_0020"),
        ("upgrade", "20260805_0021:20260805_0022"),
        ("downgrade", "20260805_0022:20260805_0021"),
        ("upgrade", "20260805_0022:20260805_0023"),
        ("downgrade", "20260805_0023:20260805_0022"),
        ("upgrade", "20260805_0023:20260805_0024"),
        ("downgrade", "20260805_0024:20260805_0023"),
        ("upgrade", "20260805_0024:20260805_0025"),
        ("downgrade", "20260805_0025:20260805_0024"),
        ("upgrade", "20260805_0025:20260805_0026"),
        ("downgrade", "20260805_0026:20260805_0025"),
        ("upgrade", "20260805_0026:20260805_0027"),
        ("downgrade", "20260805_0027:20260805_0026"),
        ("upgrade", "20260805_0027:20260805_0028"),
        ("downgrade", "20260805_0028:20260805_0027"),
        ("upgrade", "20260805_0028:20260805_0029"),
        ("downgrade", "20260805_0029:20260805_0028"),
        ("upgrade", "20260807_0043:20260809_0044"),
        ("downgrade", "20260809_0044:20260807_0043"),
        ("upgrade", "20260809_0044:20260809_0045"),
        ("downgrade", "20260809_0045:20260809_0044"),
        ("upgrade", "20260809_0045:20260809_0046"),
        ("downgrade", "20260809_0046:20260809_0045"),
        ("upgrade", "20260809_0046:20260817_0047"),
        ("downgrade", "20260817_0047:20260809_0046"),
        ("upgrade", "20260817_0047:20260817_0048"),
        ("downgrade", "20260817_0048:20260817_0047"),
    )

    for command, revision_range in ranges:
        rendered = _run(
            command,
            revision_range,
            "--sql",
            database_url=POSTGRES_OFFLINE_URL,
        )
        output = f"{rendered.stdout}\n{rendered.stderr}".lower()
        assert "mockconnection" not in output
        assert "no inspection system is available" not in output
        assert "not an executable object" not in output
        assert "traceback" not in output


def test_fresh_sqlite_full_downgrade_to_base_and_reupgrade(tmp_path: Path) -> None:
    database_path = tmp_path / "full-migration-cycle.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    _run("upgrade", "head", database_url=database_url)
    _assert_head(database_url)
    _assert_partial_default_index(database_path)

    _run("downgrade", "base", database_url=database_url)
    current = _run("current", database_url=database_url)
    output = f"{current.stdout}\n{current.stderr}"
    assert HEAD_REVISION not in output

    with sqlite3.connect(database_path) as connection:
        version_table = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'alembic_version'"
        ).fetchone()
        if version_table is not None:
            rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
            assert rows == []

    _run("upgrade", "head", database_url=database_url)
    _assert_head(database_url)
    _assert_partial_default_index(database_path)


def test_online_downgrade_guards_remain_explicit_and_offline_safe() -> None:
    guarded_migrations = {
        "20260804_0020_tunisia_direct_order_foundation.py": (
            "Downgrade blocked: customer direct-order audit exists",
            "context.is_offline_mode()",
        ),
        "20260805_0021_contract_completion.py": (
            "Downgrade blocked: completed commercial contract exists",
            "context.is_offline_mode()",
        ),
        "20260805_0022_payment_evidence_verification.py": (
            "Downgrade blocked: payment evidence or verification exists",
            "context.is_offline_mode()",
        ),
        "20260805_0023_subscription_activation.py": (
            "Downgrade blocked: automatic subscription activation exists",
            "context.is_offline_mode()",
        ),
        "20260805_0024_payment_reconciliation.py": (
            "Downgrade blocked: payment reconciliation cases exist",
            "context.is_offline_mode()",
        ),
        "20260805_0025_commercial_notification_outbox.py": (
            "Downgrade blocked: commercial notification outbox rows exist",
            "context.is_offline_mode()",
        ),
        "20260805_0026_lemon_squeezy_webhook_inbox.py": (
            "Downgrade blocked: Lemon Squeezy webhook inbox rows exist",
            "context.is_offline_mode()",
        ),
        "20260805_0027_lemon_squeezy_reconciliation_decisions.py": (
            "Downgrade blocked: Lemon Squeezy reconciliation decisions exist",
            "context.is_offline_mode()",
        ),
        "20260805_0028_subscription_runtime_quotas_usage.py": (
            "Downgrade blocked: subscription runtime, quota, or usage rows exist",
            "context.is_offline_mode()",
        ),
        "20260805_0029_subscription_runtime_transitions.py": (
            "Downgrade blocked: subscription runtime transitions exist",
            "context.is_offline_mode()",
        ),
        "20260809_0045_assessment_subscription_activation.py": (
            "Downgrade blocked: assessment subscription activation bindings exist",
            "context.is_offline_mode()",
        ),
        "20260809_0046_assessment_commercial_terms.py": (
            "Downgrade blocked: assessment commercial terms bindings exist",
            "context.is_offline_mode()",
        ),
        "20260817_0047_commercial_offer_provenance.py": (
            "Downgrade blocked: commercial offer provenance records exist",
            "context.is_offline_mode()",
        ),
        "20260817_0048_commercial_offer_provider_binding.py": (
            "Downgrade blocked: commercial offer provider bindings exist",
            "context.is_offline_mode()",
        ),
    }

    versions = ROOT / "alembic" / "versions"
    for filename, markers in guarded_migrations.items():
        source = (versions / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in source
        assert "op.get_bind()" in source
