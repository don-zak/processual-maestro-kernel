from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260807_0039_top_up_quota_grants.py"


def test_top_up_quota_migration_has_sqlite_safe_json_path():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "def _online_json_fragments(dialect_name: str)" in source
    assert 'if dialect_name == "sqlite"' in source
    assert '":entitlements"' in source
    assert '"CAST(entitlement_codes AS TEXT) IN (\'[]\', \'null\')"' in source
    assert "connection.dialect.name" in source


def test_postgresql_json_semantics_remain_explicit():
    source = MIGRATION.read_text(encoding="utf-8")

    assert '"CAST(:entitlements AS json)"' in source
    assert '"entitlement_codes::text IN (\'[]\', \'null\')"' in source
    assert "Top-up migration found quota cycles without authoritative entitlements" in source
