import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260723_0009_account_recovery_foundation.py"
ALEMBIC_INI = ROOT / "alembic.ini"


def _alembic_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/maestro",
    )
    return environment


def _offline(*arguments: str) -> str:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(ALEMBIC_INI),
            *arguments,
        ],
        cwd=ROOT,
        env=_alembic_environment(),
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def test_migration_metadata_is_linear_and_exact() -> None:
    namespace: dict[str, object] = {}
    exec(compile(MIGRATION.read_text(encoding="utf-8"), MIGRATION, "exec"), namespace)

    assert namespace["revision"] == "20260723_0009"
    assert namespace["down_revision"] == "20260723_0008"
    assert namespace["branch_labels"] is None
    assert namespace["depends_on"] is None


def test_offline_upgrade_creates_hash_only_recovery_table() -> None:
    sql = _offline("upgrade", "20260723_0009", "--sql").lower()

    assert "create table auth_account_recovery_requests" in sql
    assert "verification_token_hash" in sql
    assert "completion_token_hash" in sql
    assert "platform_account_recovery" in sql
    assert "attempt_count >= 0" in sql
    assert "identity_users" in sql
    assert "identity_user_email_addresses" in sql
    assert "on delete cascade" in sql
    assert "on delete set null" in sql

    forbidden_columns = (
        "\n\ttoken ",
        "\n\tverification_token ",
        "\n\tcompletion_token ",
        "\n\tpassword ",
        "\n\tnew_password ",
        "\n\traw_token ",
        "\n\traw_secret ",
        "\n\tapi_key ",
        "\n\taccess_token ",
        "\n\trefresh_token ",
    )

    for marker in forbidden_columns:
        assert marker not in sql


def test_offline_upgrade_creates_required_indexes() -> None:
    sql = _offline("upgrade", "20260723_0009", "--sql").lower()

    assert "ix_auth_account_recovery_user_state" in sql
    assert "ix_auth_account_recovery_expiry" in sql


def test_offline_downgrade_removes_recovery_table() -> None:
    sql = _offline(
        "downgrade",
        "20260723_0009:20260723_0008",
        "--sql",
    ).lower()

    assert "drop table auth_account_recovery_requests" in sql


def test_migration_source_contains_no_runtime_or_secret_operations() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()

    forbidden = (
        "requests.",
        "httpx.",
        "socket.",
        "subprocess.",
        "redis.",
        "secrets.token",
        "getpass.",
        "password_hash",
        "token_value",
        "raw_token",
        "raw_secret",
    )

    for marker in forbidden:
        assert marker not in source
