from __future__ import annotations

import ast
from pathlib import Path

MIGRATION = Path("alembic/versions/20260729_0013_commercial_top_up_persistence.py")


def _tree() -> ast.Module:
    return ast.parse(MIGRATION.read_text(encoding="utf-8"))


def test_migration_declares_single_parent_revision() -> None:
    assignments = {
        node.target.id: node.value
        for node in _tree().body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    revision = assignments["revision"]
    down_revision = assignments["down_revision"]
    assert isinstance(revision, ast.Constant)
    assert revision.value == "20260729_0013"
    assert isinstance(down_revision, ast.Constant)
    assert isinstance(down_revision.value, str)
    assert down_revision.value


def test_upgrade_and_downgrade_exist() -> None:
    functions = {node.name for node in _tree().body if isinstance(node, ast.FunctionDef)}
    assert {"upgrade", "downgrade"} <= functions


def test_migration_contains_all_top_up_tables_and_constraints() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    required = (
        "commercial_top_up_orders",
        "commercial_top_up_payment_evidence",
        "commercial_top_up_grants",
        "commercial_top_up_audit_records",
        "uq_commercial_top_up_orders_idempotency_key",
        "uq_commercial_top_up_payment_provider_reference",
        "uq_commercial_top_up_grants_idempotency_key",
        "uq_commercial_top_up_grants_order_id",
        "uq_commercial_top_up_audit_event_ref",
        'ondelete="CASCADE"',
        'ondelete="RESTRICT"',
    )
    for value in required:
        assert value in text
