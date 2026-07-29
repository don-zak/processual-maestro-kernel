import ast
from pathlib import Path

MODULE = Path("processual_api/billing/commercial_quota_top_up_contracts.py")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_top_up_contract_has_no_network_or_persistence_dependency() -> None:
    modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")

    forbidden = (
        "sqlalchemy",
        "requests",
        "httpx",
        "redis",
        "stripe",
        "lemonsqueezy",
    )
    for module in modules:
        assert not any(item in module.lower() for item in forbidden)


def test_top_up_contract_executes_no_side_effects() -> None:
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
        "delete",
        "execute",
        "flush",
        "post",
        "put",
        "send",
        "write",
    }
    assert calls.isdisjoint(forbidden)


def test_all_activation_flags_are_false() -> None:
    protected = {
        "TOP_UP_PURCHASE_ENABLED",
        "TOP_UP_CHECKOUT_ENABLED",
        "TOP_UP_GRANT_ENABLED",
        "TOP_UP_PERSISTENCE_ENABLED",
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
