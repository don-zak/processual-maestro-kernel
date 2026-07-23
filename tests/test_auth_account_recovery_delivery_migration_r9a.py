from pathlib import Path

MIGRATION = Path("alembic/versions/20260723_0010_account_recovery_delivery_authority.py")


def test_account_recovery_delivery_revision_extends_0009() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "20260723_0010"' in source
    assert 'down_revision = "20260723_0009"' in source


def test_migration_adds_exactly_one_delivery_authority() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert "account_recovery_request_id" in source
    assert "action_token_id IS NOT NULL" in source
    assert "account_recovery_request_id IS NULL" in source
    assert "action_token_id IS NULL" in source
    assert "account_recovery_request_id IS NOT NULL" in source
    assert "account_recovery_verification" in source


def test_downgrade_restores_action_token_only_contract() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    downgrade = source.split("def downgrade()", 1)[1]

    assert "drop_column" in downgrade
    assert '"account_recovery_request_id"' in downgrade
    assert "nullable=False" in downgrade
    assert (
        "account_recovery_verification"
        not in (
            downgrade.split(
                "ADD CONSTRAINT",
                1,
            )[1].split(
                "op.drop_constraint",
                1,
            )[0]
        )
    )
