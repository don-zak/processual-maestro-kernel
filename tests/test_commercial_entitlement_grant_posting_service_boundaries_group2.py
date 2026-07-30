import ast
from pathlib import Path

SERVICE = Path("processual_api/billing/commercial_entitlement_grant_posting_service.py")


def test_service_has_no_runtime_or_provider_imports() -> None:
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
        "lemonsqueezy",
        "redis",
        "sqlalchemy",
        "settings",
        "router",
        "runtime",
    )
    for module in modules:
        assert not any(value in module.lower() for value in forbidden)


def test_service_does_not_use_legacy_stores_or_webhooks() -> None:
    text = SERVICE.read_text(encoding="utf-8").lower()
    for value in (
        "quota_store",
        "plan_store",
        "direct_balance_update",
    ):
        assert value not in text


def test_service_exposes_required_operations() -> None:
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))
    methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)}
    assert {
        "post_monthly_subscription_grant",
        "post_top_up_grant",
        "post_refund_reversal",
        "post_usage_reversal",
        "post_admin_adjustment",
    } <= methods
