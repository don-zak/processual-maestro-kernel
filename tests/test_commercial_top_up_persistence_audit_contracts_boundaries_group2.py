import ast
from pathlib import Path

MODULE = Path("processual_api/billing/commercial_top_up_persistence_audit_contracts.py")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_contracts_define_ports_without_concrete_storage_dependency() -> None:
    modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")

    forbidden = (
        "sqlalchemy",
        "redis",
        "psycopg",
        "sqlite",
        "requests",
        "httpx",
    )
    for module in modules:
        assert not any(item in module.lower() for item in forbidden)


def test_contracts_execute_no_storage_or_network_side_effects() -> None:
    calls: set[str] = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)

    forbidden = {
        "commit",
        "execute",
        "flush",
        "post",
        "put",
        "send",
        "write",
    }
    assert calls.isdisjoint(forbidden)


def test_all_storage_activation_flags_are_false() -> None:
    protected = {
        "TOP_UP_ORDER_STORAGE_ENABLED",
        "TOP_UP_PAYMENT_EVIDENCE_STORAGE_ENABLED",
        "TOP_UP_GRANT_STORAGE_ENABLED",
        "TOP_UP_AUDIT_STORAGE_ENABLED",
        "TOP_UP_RECONCILIATION_EXECUTION_ENABLED",
    }
    values: dict[str, bool] = {}

    for node in _tree().body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id not in protected:
            continue
        assert isinstance(node.value, ast.Constant)
        values[node.target.id] = node.value.value

    assert values == {name: False for name in protected}
