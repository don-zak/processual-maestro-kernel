import importlib.util
from pathlib import Path
from types import ModuleType


MIGRATION = Path("alembic/versions/20260807_0039_top_up_quota_grants.py")


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0039", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_entitlement_backfill_uses_typed_json_for_postgresql():
    migration = _load_migration()
    predicate = migration._empty_entitlements_predicate("postgresql")
    source = MIGRATION.read_text(encoding="utf-8")

    assert "entitlement_codes::jsonb = '[]'::jsonb" in predicate
    assert "entitlement_codes::jsonb = 'null'::jsonb" in predicate
    assert '"CAST(:entitlements AS json)"' in source


def test_entitlement_backfill_uses_sqlite_compatible_predicate():
    migration = _load_migration()
    predicate = migration._empty_entitlements_predicate("sqlite")
    source = MIGRATION.read_text(encoding="utf-8")

    assert "::json" not in predicate
    assert "entitlement_codes = '[]'" in predicate
    assert "entitlement_codes = 'null'" in predicate
    assert 'else ":entitlements"' in source
