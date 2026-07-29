import ast
from pathlib import Path

MODULE = Path("processual_api/billing/commercial_ui_contracts.py")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_contracts_have_no_frontend_framework_dependency() -> None:
    tree = _tree()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")

    forbidden = (
        "react",
        "vue",
        "svelte",
        "next",
        "vite",
        "tailwind",
    )
    for module in modules:
        assert not any(item in module.lower() for item in forbidden)


def test_contracts_do_not_execute_commercial_actions() -> None:
    tree = _tree()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)

    forbidden = {
        "charge",
        "commit",
        "invoice",
        "settle",
        "write",
        "write_text",
        "open",
    }
    assert calls.isdisjoint(forbidden)
