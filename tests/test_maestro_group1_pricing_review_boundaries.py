import ast
from pathlib import Path

MODULE = Path("processual_api/billing/maestro_group1_pricing_review.py")


def _tree() -> ast.Module:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_review_does_not_import_runtime_or_payment_execution() -> None:
    tree = _tree()
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imported_modules.add(node.module or "")
    forbidden_fragments = (
        "processual_api.adapters",
        "agent_runtime",
        "checkout",
        "invoice",
        "settlement",
        "payment",
        "lemon",
        "shadow_store",
    )
    for module_name in imported_modules:
        assert not any(fragment in module_name for fragment in forbidden_fragments)


def test_review_does_not_execute_or_persist() -> None:
    tree = _tree()
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            called_names.add(node.func.id)
        if isinstance(node.func, ast.Attribute):
            called_names.add(node.func.attr)
    forbidden_calls = {
        "run_agent",
        "append_best_effort",
        "write",
        "write_text",
        "write_bytes",
        "open",
        "commit",
        "charge",
        "invoice",
        "settle",
    }
    assert called_names.isdisjoint(forbidden_calls)


def test_review_contains_no_secret_or_raw_payload_fields() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    forbidden_fields = (
        "api_key",
        "access_token",
        "refresh_token",
        "client_secret",
        "provider_secret",
        "raw_prompt",
        "raw_response",
        "raw_agent_output",
        "task_content",
        "document_content",
    )
    for field_name in forbidden_fields:
        assert field_name not in source


def test_all_commercial_approval_flags_remain_false() -> None:
    source = MODULE.read_text(encoding="utf-8")
    required_false_flags = (
        "COMMERCIAL_ENFORCEMENT_ENABLED: Final = False",
        "APPROVED_FOR_QUOTA: Final = False",
        "APPROVED_FOR_PRICING: Final = False",
        "APPROVED_FOR_INVOICING: Final = False",
        "APPROVED_FOR_CHECKOUT: Final = False",
        "APPROVED_FOR_SETTLEMENT: Final = False",
        "PROVIDER_COST_INCLUDED: Final = False",
    )
    for flag in required_false_flags:
        assert flag in source
