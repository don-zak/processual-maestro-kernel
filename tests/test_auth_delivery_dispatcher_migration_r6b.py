from pathlib import Path


def test_dispatcher_migration_extends_email_verification_head():
    source = Path(
        "alembic/versions/20260722_0005_auth_delivery_dispatcher.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260722_0005"' in source
    assert 'down_revision: str | None = "20260722_0004"' in source
    assert '"claim_id"' in source
    assert '"dead_lettered_at"' in source
    assert '"ix_auth_delivery_outbox_dispatch"' in source
