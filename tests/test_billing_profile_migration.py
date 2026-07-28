from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260728_0012_customer_billing_profiles.py"
ALEMBIC_INI = ROOT / "alembic.ini"


def _offline(*arguments: str) -> str:
    environment = os.environ.copy()
    environment.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost:5432/maestro",
    )

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
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    return completed.stdout.lower()


def test_billing_profile_migration_is_linear_and_exact() -> None:
    namespace: dict[str, object] = {}

    exec(
        compile(
            MIGRATION.read_text(encoding="utf-8"),
            MIGRATION,
            "exec",
        ),
        namespace,
    )

    assert namespace["revision"] == "20260728_0012"
    assert namespace["down_revision"] == "20260727_0011"
    assert namespace["branch_labels"] is None
    assert namespace["depends_on"] is None


def test_billing_profile_upgrade_creates_table_and_security_constraints() -> None:
    sql = _offline(
        "upgrade",
        "20260728_0012",
        "--sql",
    )

    required = (
        "create table customer_billing_profiles",
        "identity_users",
        "identity_organizations",
        "on delete cascade",
        "on delete set null",
        "country_code = upper(country_code)",
        "review_required",
        "disabled",
        "uq_customer_billing_profiles_personal",
        "uq_customer_billing_profiles_organization",
        "organization_id is null",
        "organization_id is not null",
    )

    for marker in required:
        assert marker in sql


def test_billing_profile_downgrade_removes_table() -> None:
    sql = _offline(
        "downgrade",
        "20260728_0012:20260727_0011",
        "--sql",
    )

    assert "drop table customer_billing_profiles" in sql


def test_billing_profile_migration_contains_no_payment_secrets() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()

    forbidden = (
        "card_number",
        "cvv",
        "bank_account",
        "raw_secret",
        "access_token",
        "refresh_token",
        "payment_evidence",
        "webhook_signature",
        "httpx.",
        "requests.",
        "socket.",
    )

    for marker in forbidden:
        assert marker not in source
