from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260807_0039_top_up_quota_grants.py"


def test_top_up_migration_compares_json_through_text_projection():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "entitlement_codes::text IN ('[]', 'null')" in source
    assert "entitlement_codes = '[]'" not in source
    assert "entitlement_codes = 'null'" not in source


def test_top_up_migration_casts_entitlement_payload_to_json():
    source = MIGRATION.read_text(encoding="utf-8")

    assert "CAST(:entitlements AS json)" in source
    assert "::json" in source
