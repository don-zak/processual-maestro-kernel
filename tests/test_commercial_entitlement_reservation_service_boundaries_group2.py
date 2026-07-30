from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "processual_api" / "billing" / "commercial_entitlement_reservation_service.py"


def parsed_tree() -> ast.Module:
    return ast.parse(SERVICE.read_text(encoding="utf-8-sig"))


def imported_modules() -> set[str]:
    modules: set[str] = set()

    for node in ast.walk(parsed_tree()):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)

    return modules


def test_service_does_not_import_legacy_quota_store() -> None:
    modules = imported_modules()

    assert "processual_api.billing.quota_store" not in modules
    assert "processual_api.quota_store" not in modules


def test_service_does_not_import_runtime_or_routers() -> None:
    modules = imported_modules()

    assert not any(module.startswith("processual_api.routers") for module in modules)
    assert not any(module.endswith("_runtime") for module in modules)


def test_service_has_no_sqlalchemy_dependency() -> None:
    modules = imported_modules()

    assert not any(module == "sqlalchemy" or module.startswith("sqlalchemy.") for module in modules)


def test_service_does_not_read_environment_or_settings() -> None:
    modules = imported_modules()

    assert "os" not in modules
    assert "processual_api.settings" not in modules


def test_service_exposes_three_lifecycle_operations() -> None:
    tree = parsed_tree()

    service_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "EntitlementReservationService"
    )

    methods = {
        node.name
        for node in service_class.body
        if isinstance(
            node,
            ast.AsyncFunctionDef,
        )
    }

    assert {
        "reserve_units",
        "commit_reservation",
        "release_reservation",
    }.issubset(methods)


def test_all_activation_flags_are_literal_false() -> None:
    tree = parsed_tree()

    expected = {
        "ENTITLEMENT_RESERVATION_SERVICE_ENABLED",
        "ENTITLEMENT_RESERVATION_WRITES_ENABLED",
        "ENTITLEMENT_RESERVATION_RUNTIME_WIRING_ENABLED",
        ("ENTITLEMENT_RESERVATION_COMMERCIAL_ENFORCEMENT_ENABLED"),
    }
    observed: dict[str, object] = {}

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
