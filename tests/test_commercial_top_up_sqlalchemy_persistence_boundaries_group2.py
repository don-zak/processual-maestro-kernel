import ast
from pathlib import Path

FILES = (
    Path("processual_api/billing/commercial_top_up_models.py"),
    Path("processual_api/billing/commercial_top_up_repositories.py"),
    Path("processual_api/billing/commercial_top_up_unit_of_work.py"),
)


def test_sqlalchemy_layer_has_no_payment_or_network_client() -> None:
    modules: set[str] = set()
    for path in FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")

    forbidden = ("requests", "httpx", "stripe", "lemonsqueezy", "redis")
    for module in modules:
        assert not any(value in module.lower() for value in forbidden)


def test_uow_is_async_and_rollback_safe() -> None:
    tree = ast.parse(FILES[2].read_text(encoding="utf-8"))
    async_methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}
    assert {"__aenter__", "__aexit__", "commit", "rollback"} <= async_methods


def test_audit_repository_exposes_append_not_update_or_delete() -> None:
    tree = ast.parse(FILES[1].read_text(encoding="utf-8"))
    methods = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "append" in methods
    assert "update" not in methods
    assert "delete" not in methods
