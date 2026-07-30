import ast
from pathlib import Path

SOURCE = Path("processual_api/billing/commercial_subscription_cycle_grant_service.py")


def test_monthly_grant_service_has_no_checkout_or_network_imports() -> None:
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
        "stripe",
        "lemonsqueezy",
        "router",
        "webhook",
    )
    for module in modules:
        assert not any(token in module.lower() for token in forbidden)


def test_cycle_authority_and_fail_closed_markers_exist() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    required = (
        "ApprovedSubscriptionCycleGrantCommand",
        "subscription-billing-authority:",
        "billing-cycle-approval:",
        "deterministic_cycle_idempotency",
        "rollover_preserved",
        "subscription_activation_performed",
    )
    for marker in required:
        assert marker in text
