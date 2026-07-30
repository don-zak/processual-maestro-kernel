import ast
from pathlib import Path

SOURCE = Path("processual_api/billing/commercial_subscription_checkout_service.py")


def imported_modules() -> set[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")

    return modules


def test_checkout_authority_has_no_provider_or_http_imports() -> None:
    modules = imported_modules()
    forbidden = (
        "requests",
        "httpx",
        "stripe",
        "lemonsqueezy",
        "fastapi",
        "router",
        "webhook",
    )

    for module in modules:
        assert not any(token in module.lower() for token in forbidden)


def test_no_environment_or_settings_dependency() -> None:
    modules = imported_modules()
    assert "os" not in modules
    assert "processual_api.settings" not in modules


def test_all_runtime_activation_flags_are_literal_false() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    expected = {
        "COMMERCIAL_CHECKOUT_AUTHORITY_ENABLED",
        "COMMERCIAL_CHECKOUT_WRITES_ENABLED",
        "COMMERCIAL_CHECKOUT_PROVIDER_RUNTIME_ENABLED",
        "COMMERCIAL_CHECKOUT_WEBHOOK_RUNTIME_ENABLED",
        "COMMERCIAL_CHECKOUT_ACTIVATION_ENABLED",
        "COMMERCIAL_CHECKOUT_GRANT_BRIDGE_ENABLED",
    }
    observed = {}

    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id not in expected:
            continue
        assert isinstance(node.value, ast.Constant)
        observed[node.target.id] = node.value.value

    assert observed == {name: False for name in expected}


def test_governing_markers_are_present() -> None:
    content = SOURCE.read_text(encoding="utf-8")
    required = (
        "platform_admin authority is required",
        "recent MFA step-up is required",
        "verified payment evidence is required before activation",
        "Payment provider events are evidence only.",
        "customer channel choice must remain preserved",
        "subscription-billing-authority:",
        "billing-cycle-approval:",
        "webhook_direct_grant_prohibited",
    )

    for marker in required:
        assert marker in content
