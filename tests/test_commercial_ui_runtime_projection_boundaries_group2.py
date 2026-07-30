import ast
from pathlib import Path

SOURCE = Path("processual_api/billing/commercial_ui_runtime_projection.py")


def _tree() -> ast.Module:
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_projection_has_no_frontend_framework_dependency() -> None:
    modules: set[str] = set()

    for node in ast.walk(_tree()):
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


def test_projection_cannot_execute_commercial_actions() -> None:
    calls: set[str] = set()

    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)

    forbidden = {
        "charge",
        "commit",
        "execute",
        "invoice",
        "publish",
        "settle",
        "write",
        "write_text",
        "open",
        "post_monthly_subscription_grant",
        "decide_activation",
        "record_payment_evidence",
    }

    assert calls.isdisjoint(forbidden)


def test_all_runtime_flags_are_literal_false() -> None:
    expected = {
        "COMMERCIAL_UI_RUNTIME_PROJECTION_ENABLED",
        "COMMERCIAL_UI_ACTIONS_ENABLED",
        "COMMERCIAL_UI_POLLING_ENABLED",
        "COMMERCIAL_UI_REALTIME_STREAM_ENABLED",
    }
    observed = {}

    for node in _tree().body:
        if not isinstance(node, ast.AnnAssign):
            continue
        if not isinstance(node.target, ast.Name):
            continue
        if node.target.id not in expected:
            continue
        assert isinstance(node.value, ast.Constant)
        observed[node.target.id] = node.value.value

    assert observed == {name: False for name in expected}
