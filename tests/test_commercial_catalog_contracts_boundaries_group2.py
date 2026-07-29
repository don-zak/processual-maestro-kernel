import ast
from pathlib import Path

MODULE = Path("processual_api/billing/commercial_catalog_contracts.py")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_catalog_contract_has_no_persistence_or_network_dependency() -> None:
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
        assert not any(name in module.lower() for name in forbidden)


def test_catalog_contract_executes_no_commercial_side_effects() -> None:
    calls: set[str] = set()
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)

    forbidden = {
        "add",
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


def test_no_runtime_activation_constants_are_true() -> None:
    tree = _tree()
    protected = {
        "CATALOG_PUBLICATION_APPROVED",
        "OFFER_PURCHASE_ENABLED",
        "ENTITLEMENT_GRANT_ENABLED",
        "QUOTA_ENFORCEMENT_ENABLED",
        "SUBSCRIPTION_MIGRATION_ENABLED",
    }
    values: dict[str, bool] = {}
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id not in protected:
            continue
        assert isinstance(node.value, ast.Constant)
        values[node.target.id] = node.value.value

    assert values == {name: False for name in protected}
