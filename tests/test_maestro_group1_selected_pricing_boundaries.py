import ast
from pathlib import Path

MODULE = Path("processual_api/billing/maestro_group1_selected_pricing.py")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_selected_pricing_has_no_runtime_or_payment_imports() -> None:
    tree = _tree()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")

    forbidden = (
        "agent_runtime",
        "checkout",
        "invoice",
        "payment",
        "settlement",
        "shadow_store",
        "lemon",
    )
    for module_name in imported_modules:
        assert not any(item in module_name for item in forbidden)


def test_selected_pricing_does_not_persist_or_execute() -> None:
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
        "append_best_effort",
        "charge",
        "commit",
        "invoice",
        "open",
        "run_agent",
        "settle",
        "write",
        "write_bytes",
        "write_text",
    }
    assert calls.isdisjoint(forbidden)


def test_selected_pricing_contains_no_secrets_or_raw_payloads() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    forbidden = (
        "api_key",
        "access_token",
        "client_secret",
        "provider_secret",
        "raw_prompt",
        "raw_response",
        "task_content",
        "document_content",
    )
    for item in forbidden:
        assert item not in source
