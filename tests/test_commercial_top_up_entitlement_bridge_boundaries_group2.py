import ast
from pathlib import Path

BRIDGE = Path("processual_api/billing/commercial_top_up_entitlement_bridge.py")


def test_bridge_has_no_network_checkout_or_runtime_imports() -> None:
    tree = ast.parse(BRIDGE.read_text(encoding="utf-8"))
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
        "router",
        "webhook",
    )
    for module in modules:
        assert not any(value in module.lower() for value in forbidden)


def test_bridge_requires_one_atomic_unit_of_work() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "AtomicTopUpEntitlementUnitOfWork" in text
    assert "single_database_transaction_required" in text
    assert "payment_grant_audit_ledger_atomic" in text
