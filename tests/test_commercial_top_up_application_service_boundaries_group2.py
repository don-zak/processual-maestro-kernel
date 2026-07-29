import ast
from pathlib import Path

SERVICE = Path("processual_api/billing/commercial_top_up_application_service.py")


def test_service_has_no_network_payment_or_balance_client() -> None:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")

    forbidden = (
        "requests",
        "httpx",
        "stripe",
        "lemonsqueezy",
        "redis",
    )
    for module in modules:
        assert not any(value in module.lower() for value in forbidden)


def test_service_exposes_async_atomic_operations() -> None:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    async_methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}

    assert {"create_order", "record_payment_and_grant"} <= async_methods


def test_service_does_not_mutate_entitlement_or_quota_store() -> None:
    text = SERVICE.read_text(encoding="utf-8").lower()

    forbidden = (
        "quota_store",
        "entitlement_store",
        "increment_balance",
        "decrement_balance",
        "apply_units_to_balance",
    )
    for marker in forbidden:
        assert marker not in text
