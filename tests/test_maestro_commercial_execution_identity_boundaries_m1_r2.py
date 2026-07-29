import ast
from pathlib import Path

MODULE_PATH = Path("processual_api/billing/maestro_commercial_execution_identity.py")
ALLOWED_INTERNAL_IMPORTS = {
    "processual_api.billing.maestro_execution_authority",
}
FORBIDDEN_IMPORT_FRAGMENTS = {
    "adapters",
    "auth.delivery",
    "cgt_governor",
    "connectors",
    "integrations",
    "redis",
    "sqlalchemy",
    "database",
    "shadow_measurements",
    "shadow_store",
    "subscriptions",
    "checkout",
    "invoice",
    "payment",
    "settlement",
    "quota",
}
FORBIDDEN_RUNTIME_CALLS = {
    "open",
    "connect",
    "execute",
    "commit",
    "send",
    "publish",
    "dispatch",
    "generate",
    "run_agent",
}
FALSE_BOUNDARY_ASSIGNMENTS = {
    "RUNTIME_INTEGRATION_ENABLED",
    "MEASUREMENT_EMISSION_ENABLED",
    "SHADOW_STORE_WRITES_ENABLED",
    "COMMERCIAL_ENFORCEMENT_ENABLED",
    "APPROVED_FOR_QUOTA",
    "APPROVED_FOR_INVOICING",
    "APPROVED_FOR_CHECKOUT",
    "APPROVED_FOR_SETTLEMENT",
    "PLATFORM_OWNED_LLM_KEYS_ALLOWED",
    "RAW_SECRETS_ALLOWED",
    "RAW_PROMPTS_ALLOWED",
    "RAW_RESPONSES_ALLOWED",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8-sig"))


def test_module_imports_only_existing_authority_contract() -> None:
    imported_modules: set[str] = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    project_imports = {module for module in imported_modules if module.startswith("processual_api.")}
    assert project_imports == ALLOWED_INTERNAL_IMPORTS
    for module in imported_modules:
        lowered = module.lower()
        assert not any(fragment in lowered for fragment in FORBIDDEN_IMPORT_FRAGMENTS)


def test_module_has_no_runtime_side_effect_calls() -> None:
    called_names = {
        node.func.id for node in ast.walk(_tree()) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert called_names.isdisjoint(FORBIDDEN_RUNTIME_CALLS)


def test_all_runtime_and_commercial_boundaries_remain_false() -> None:
    assignments: dict[str, object] = {}
    for node in _tree().body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
            assignments[target.id] = node.value.value
    for name in FALSE_BOUNDARY_ASSIGNMENTS:
        assert assignments[name] is False


def test_byok_policy_is_literal_and_platform_key_is_forbidden() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8-sig")
    assert 'LLM_CONNECTION_POLICY = "byok_only"' in source
    assert "PLATFORM_OWNED_LLM_KEYS_ALLOWED = False" in source
    assert "CUSTOMER_BYOK" in source


def test_contract_does_not_define_observer_store_or_measurement() -> None:
    class_names = {node.name for node in ast.walk(_tree()) if isinstance(node, ast.ClassDef)}
    assert not any("Observer" in name for name in class_names)
    assert not any("Store" in name for name in class_names)
    assert not any("Measurement" in name for name in class_names)


def test_contract_does_not_mutate_runtime_interfaces() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8-sig")
    assert "RuntimeAdapter" not in source
    assert "AgentExecutionResult" not in source
    assert "BaseLLMAdapter" not in source


def test_only_agent_runtime_is_supported_in_m1_r2() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8-sig")
    assert "MaestroExecutionAuthorityKind.AGENT_RUNTIME" in source
    assert "MaestroExecutionAuthorityKind.LLM_ADAPTER" not in source
