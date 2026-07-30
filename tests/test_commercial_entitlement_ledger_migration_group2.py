from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
from types import ModuleType

from processual_api.billing.commercial_entitlement_ledger_schema_contracts import (
    BALANCES_TABLE,
    LEDGER_ENTRIES_TABLE,
    RESERVATION_LOCKS_TABLE,
    build_entitlement_schema_contracts,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "20260730_0015_commercial_entitlement_ledger.py"
ALEMBIC_ENV_PATH = ROOT / "alembic" / "env.py"


def load_migration() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "entitlement_ledger_migration_0015",
        MIGRATION_PATH,
    )
    assert specification is not None
    assert specification.loader is not None

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_migration_revision_chain() -> None:
    migration = load_migration()

    assert migration.revision == "20260730_0015"
    assert migration.down_revision == "20260729_0014"
    assert migration.branch_labels is None
    assert migration.depends_on is None


def test_migration_declares_canonical_tables() -> None:
    migration = load_migration()

    assert migration.LEDGER_TABLE == LEDGER_ENTRIES_TABLE
    assert migration.BALANCE_TABLE == BALANCES_TABLE
    assert migration.RESERVATION_LOCK_TABLE == (RESERVATION_LOCKS_TABLE)


def test_upgrade_and_downgrade_are_callable() -> None:
    migration = load_migration()

    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_source_creates_and_drops_three_tables() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert source.count("op.create_table(") == 3
    assert source.count("op.drop_table(") == 3

    for table_name in (
        LEDGER_ENTRIES_TABLE,
        BALANCES_TABLE,
        RESERVATION_LOCKS_TABLE,
    ):
        assert table_name in source


def test_source_contains_all_constraint_names() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    string_literals = {
        node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    for table in build_entitlement_schema_contracts():
        for constraint in table.constraints:
            assert constraint.name in string_literals


def test_source_contains_all_index_names() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    for table in build_entitlement_schema_contracts():
        for index in table.indexes:
            assert index.name in source


def test_downgrade_uses_reverse_dependency_order() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    lock_position = source.rfind("op.drop_table(RESERVATION_LOCK_TABLE)")
    balance_position = source.rfind("op.drop_table(BALANCE_TABLE)")
    ledger_position = source.rfind("op.drop_table(LEDGER_TABLE)")

    assert -1 not in (
        lock_position,
        balance_position,
        ledger_position,
    )
    assert lock_position < balance_position < ledger_position


def test_partial_postgresql_indexes_are_preserved() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert source.count("postgresql_where=") == 2
    assert "reservation_id IS NOT NULL" in source
    assert "related_entry_id IS NOT NULL" in source


def test_related_entry_foreign_key_is_restrictive() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    foreign_key_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "ForeignKeyConstraint"
    ]

    assert len(foreign_key_calls) == 1

    call = foreign_key_calls[0]
    keyword_values = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg is not None}

    name_value = keyword_values["name"]
    ondelete_value = keyword_values["ondelete"]

    assert isinstance(name_value, ast.Constant)
    assert name_value.value == ("fk_commercial_entitlement_ledger_entries_related_entry")

    assert isinstance(ondelete_value, ast.Constant)
    assert ondelete_value.value == "RESTRICT"


def test_alembic_env_registers_billing_models() -> None:
    source = ALEMBIC_ENV_PATH.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

    billing_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "processual_api.billing"
        for alias in node.names
    }

    assert "commercial_entitlement_ledger_models" in (billing_imports)
    assert "commercial_top_up_models" in billing_imports


def test_migration_identifiers_fit_postgresql_limit() -> None:
    names: list[str] = []

    for table in build_entitlement_schema_contracts():
        names.append(table.name)
        names.extend(constraint.name for constraint in table.constraints)
        names.extend(index.name for index in table.indexes)

    assert all(len(name) <= 63 for name in names)
