from __future__ import annotations

from pathlib import Path

MIGRATION = Path("alembic/versions/20260807_0039_top_up_quota_grants.py")


def test_migration_0039_uses_postgres_safe_json_comparisons_and_assignment() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "CAST(:entitlements AS JSON)" in source
    assert "entitlement_codes::text IN ('[]', 'null')" in source
    assert "entitlement_codes = '[]'" not in source
    assert "entitlement_codes = 'null'" not in source
