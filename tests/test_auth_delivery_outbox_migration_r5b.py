from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _alembic_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+asyncpg://localhost/maestro"
    return environment


def test_auth_migration_chain_has_the_current_single_head() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        check=True,
        capture_output=True,
        text=True,
        env=_alembic_environment(),
    )
    assert result.stdout.strip() == "20260723_0009 (head)"
    assert result.stdout.count("(head)") == 1


def test_delivery_outbox_offline_upgrade_and_downgrade_contracts() -> None:
    upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "20260722_0003", "--sql"],
        check=True,
        capture_output=True,
        text=True,
        env=_alembic_environment(),
    ).stdout.lower()
    assert "create table auth_delivery_outbox" in upgrade
    assert "payload_ciphertext" in upgrade
    assert "raw_action_token" not in upgrade
    assert "email_normalized" not in upgrade.split("create table auth_delivery_outbox", 1)[1]

    downgrade = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "downgrade",
            "20260722_0003:20260722_0002",
            "--sql",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=_alembic_environment(),
    ).stdout.lower()
    assert "drop table auth_delivery_outbox" in downgrade


def test_delivery_outbox_revision_has_expected_parent() -> None:
    source = Path("alembic/versions/20260722_0003_auth_delivery_outbox.py").read_text(encoding="utf-8")
    assert 'revision: str = "20260722_0003"' in source
    assert 'down_revision: str | none = "20260722_0002"' in source.lower()


def test_email_verification_revision_extends_delivery_outbox_head() -> None:
    source = Path("alembic/versions/20260722_0004_auth_email_verification_lifecycle.py").read_text(encoding="utf-8")
    assert 'revision: str = "20260722_0004"' in source
    assert 'down_revision: str | none = "20260722_0003"' in source.lower()
