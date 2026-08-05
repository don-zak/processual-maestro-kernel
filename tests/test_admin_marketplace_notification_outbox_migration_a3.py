from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "alembic/versions/20260805_0025_commercial_notification_outbox.py"


def test_notification_outbox_extends_reconciliation_head():
    namespace = {}
    exec(compile(MIGRATION.read_text(), str(MIGRATION), "exec"), namespace)
    assert namespace["revision"] == "20260805_0025"
    assert namespace["down_revision"] == "20260805_0024"


def test_migration_has_delivery_controls_and_guard():
    source = MIGRATION.read_text()
    for value in ("deduplication_key_hash", "attempt_count >= 0", "dead_lettered_at", "Downgrade blocked"):
        assert value in source
