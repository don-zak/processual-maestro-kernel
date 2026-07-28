import ast
from pathlib import Path

MODULE_PATH = Path("processual_api/billing/maestro_execution_family_evidence.py")

ALLOWED_INTERNAL_IMPORTS = {
    "processual_api.billing.maestro_execution_authority",
    "processual_api.billing.maestro_execution_authority_readiness",
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
}

FORBIDDEN_COMMERCIAL_ASSIGNMENTS = {
    "RUNTIME_INTEGRATION_ENABLED",
    "MEASUREMENT_EMISSION_ENABLED",
    "COMMERCIAL_ENFORCEMENT_ENABLED",
    "APPROVED_FOR_QUOTA",
    "APPROVED_FOR_INVOICING",
    "APPROVED_FOR_CHECKOUT",
    "APPROVED_FOR_SETTLEMENT",
}


def _tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8-sig"))


def test_module_imports_only_pure_maestro_contracts() -> None:
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
    calls = {
        node.func.id for node in ast.walk(_tree()) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert calls.isdisjoint(FORBIDDEN_RUNTIME_CALLS)


def test_all_commercial_switches_remain_false() -> None:
    assignments: dict[str, object] = {}

    for node in _tree().body:
        if not isinstance(node, ast.Assign):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not isinstance(target, ast.Name):
            continue

        if isinstance(node.value, ast.Constant):
            assignments[target.id] = node.value.value

    for name in FORBIDDEN_COMMERCIAL_ASSIGNMENTS:
        assert assignments[name] is False


def test_byok_only_policy_remains_explicit() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8-sig")

    assert 'LLM_CONNECTION_POLICY = "byok_only"' in source
    assert "PLATFORM_OWNED_LLM_KEYS_ALLOWED = False" in source


def test_module_does_not_define_an_observer_or_store() -> None:
    class_names = {node.name for node in ast.walk(_tree()) if isinstance(node, ast.ClassDef)}

    assert not any("Observer" in name for name in class_names)
    assert not any("Store" in name for name in class_names)


def test_module_does_not_create_execution_contexts() -> None:
    called_names = {
        node.func.id for node in ast.walk(_tree()) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert "MaestroExecutionAttemptContext" not in called_names
    assert "MaestroExecutionCompletion" not in called_names
