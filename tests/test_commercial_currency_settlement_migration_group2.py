import ast
from pathlib import Path

MIGRATION_PATH = Path("alembic/versions/20260729_0014_commercial_usd_tnd_settlement.py")


def _source() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8-sig")


def test_migration_revision_chain_is_linear() -> None:
    tree = ast.parse(_source())

    assignments: dict[str, object] = {}

    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue

        if not isinstance(node.target, ast.Name):
            continue

        if not isinstance(node.value, ast.Constant):
            continue

        assignments[node.target.id] = node.value.value

    assert assignments["revision"] == "20260729_0014"
    assert assignments["down_revision"] == "20260729_0013"


def test_migration_adds_fixed_settlement_columns() -> None:
    source = _source()

    for column_name in (
        "settlement_currency",
        "settlement_amount",
        "exchange_rate_usd_tnd",
        "exchange_rate_source",
        "exchange_rate_reference",
        "exchange_rate_observed_at",
        "exchange_rate_expires_at",
    ):
        assert f'"{column_name}"' in source


def test_migration_backfills_existing_orders_as_usd() -> None:
    source = _source()

    assert "settlement_currency = 'USD'" in source
    assert "settlement_amount = total_price_usd" in source


def test_migration_enforces_channel_aware_settlement() -> None:
    source = _source()

    assert "channel = 'lemon_squeezy'" in source
    assert "settlement_currency = 'USD'" in source
    assert "settlement_amount = total_price_usd" in source

    assert "channel = 'local_tunisia'" in source
    assert "settlement_currency = 'TND'" in source
    assert "exchange_rate_usd_tnd IS NOT NULL" in source
    assert "exchange_rate_expires_at" in source
    assert "exchange_rate_observed_at" in source


def test_migration_renames_verified_amount_column() -> None:
    source = _source()

    assert '"verified_amount_usd"' in source
    assert 'new_column_name="verified_amount"' in source
    assert "scale=3" in source


def test_migration_downgrade_restores_original_shape() -> None:
    source = _source()

    assert 'new_column_name="verified_amount_usd"' in source
    assert 'batch_op.drop_column("settlement_currency")' in source
    assert 'batch_op.drop_column("settlement_amount")' in source


def test_payment_amount_constraint_uses_final_database_name() -> None:
    source = _source()

    assert source.count("op.f(PAYMENT_AMOUNT_CHECK)") == 4
    assert "op.drop_constraint(" not in source
    assert "op.create_check_constraint(" not in source


def test_sqlite_sensitive_schema_changes_use_batch_mode() -> None:
    source = _source()

    assert source.count("with op.batch_alter_table(ORDER_TABLE)") == 3
    assert source.count("with op.batch_alter_table(PAYMENT_TABLE)") == 2
    assert "op.alter_column(" not in source
    assert "op.drop_constraint(" not in source
    assert "op.create_check_constraint(" not in source
    assert "op.drop_column(" not in source
