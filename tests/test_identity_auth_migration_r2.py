from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20260721_0001_identity_auth_foundation.py"
ALEMBIC_INI = ROOT / "alembic.ini"

EXPECTED_TABLES = (
    "identity_users",
    "identity_organizations",
    "identity_memberships",
    "auth_sessions",
    "auth_refresh_tokens",
    "auth_action_tokens",
    "auth_mfa_factors",
    "auth_mfa_recovery_codes",
    "auth_mfa_challenges",
)


def _run_offline_alembic(*arguments: str) -> str:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = "postgresql+asyncpg://localhost/maestro"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *arguments],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_first_identity_revision_has_no_parent_and_is_reversible() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260721_0001"' in source
    assert "down_revision: str | None = None" in source
    assert "def upgrade() -> None:" in source
    assert "def downgrade() -> None:" in source
    for table in EXPECTED_TABLES:
        assert f'"{table}"' in source
        assert f'op.drop_table("{table}")' in source


def test_offline_upgrade_emits_all_tables_without_raw_secret_columns() -> None:
    sql = _run_offline_alembic("upgrade", "head", "--sql")
    lowered = sql.lower()
    for table in EXPECTED_TABLES:
        assert f"create table {table}" in lowered

    assert "password_hash" in lowered
    assert "token_hash" in lowered
    assert "secret_ciphertext" in lowered
    assert "code_hash" in lowered
    assert "challenge_hash" in lowered
    assert "\n\tpassword " not in lowered
    assert "\n\trefresh_token " not in lowered
    assert "\n\tsecret " not in lowered
    assert "\n\trecovery_code " not in lowered


def test_offline_downgrade_drops_every_r2_table() -> None:
    sql = _run_offline_alembic("downgrade", "20260721_0001:base", "--sql")
    lowered = sql.lower()
    for table in EXPECTED_TABLES:
        assert f"drop table {table}" in lowered


def test_alembic_environment_uses_shared_metadata_and_database_url() -> None:
    environment_source = (ROOT / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "target_metadata = Base.metadata" in environment_source
    assert 'os.environ.get("DATABASE_URL"' in environment_source
    assert "postgresql+asyncpg://" in environment_source
