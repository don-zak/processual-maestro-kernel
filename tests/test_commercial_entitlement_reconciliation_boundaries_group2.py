import ast
from pathlib import Path

SOURCE = Path("processual_api/billing/commercial_entitlement_reconciliation_service.py")


def test_reconciliation_has_no_write_or_network_imports() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")

    forbidden = (
        "requests",
        "httpx",
        "router",
        "webhook",
        "compare_and_swap",
    )
    for module in modules:
        assert not any(token in module.lower() for token in forbidden)


def test_reconciliation_source_contains_no_mutation_calls() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    forbidden_calls = (
        "unit.ledger.append(",
        "unit.balances.compare_and_swap(",
        "unit.commit(",
        "unit.rollback(",
        "session.add(",
        "session.delete(",
        "session.execute(update(",
    )
    for call in forbidden_calls:
        assert call not in text

    required = (
        "automatic entitlement repair is prohibited",
        "auto_repair_performed=False",
        "list_for_subscription",
        "report_digest",
    )
    for marker in required:
        assert marker in text
