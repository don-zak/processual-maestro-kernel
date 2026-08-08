from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic/versions/20260805_0024_payment_reconciliation.py"


def test_reconciliation_migration_extends_activation_head():
    namespace = {}
    exec(compile(MIGRATION.read_text(), str(MIGRATION), "exec"), namespace)
    assert namespace["revision"] == "20260805_0024"
    assert namespace["down_revision"] == "20260805_0023"


def test_reconciliation_migration_is_audited_and_downgrade_guarded():
    source = MIGRATION.read_text()
    assert "admin_market_payment_reconciliation_cases" in source
    assert "payment_reconciliation_decided" in source
    assert "payment_reconciliation" in source
    assert "Downgrade blocked" in source
