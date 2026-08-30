from pathlib import Path


MIGRATION = Path("alembic/versions/20260807_0039_top_up_quota_grants.py")


def test_entitlement_backfill_uses_explicit_json_casts():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "SET entitlement_codes = CAST(:entitlements AS json)" in source
    assert "entitlement_codes::jsonb = '[]'::jsonb" in source
    assert "entitlement_codes::jsonb = 'null'::jsonb" in source


def test_entitlement_backfill_does_not_compare_json_to_untyped_text():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "OR entitlement_codes = '[]'" not in source
    assert "OR entitlement_codes = 'null'" not in source
