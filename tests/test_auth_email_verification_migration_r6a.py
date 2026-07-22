from pathlib import Path


def test_email_verification_migration_extends_delivery_outbox_head():
    migration = Path(
        "alembic/versions/20260722_0004_auth_email_verification_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260722_0004"' in migration
    assert 'down_revision: str | None = "20260722_0003"' in migration
    assert '"auth_action_tokens"' in migration
    assert '"invalidated_at"' in migration
    assert "DateTime(timezone=True)" in migration
