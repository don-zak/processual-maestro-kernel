from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "processual_api"
SHIM_PATH = PACKAGE_ROOT / "billing" / "subscription_catalog.py"


def _subscription_catalog_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "processual_api.billing.subscription_catalog":
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "processual_api.billing.subscription_catalog":
                violations.append(module)
            if module in {"processual_api.billing", "billing", ""}:
                for alias in node.names:
                    if alias.name == "subscription_catalog":
                        violations.append(
                            f"{module or '<relative>'}.{alias.name}"
                        )

    return violations


def test_subscription_catalog_is_not_a_runtime_dependency() -> None:
    violations: dict[str, list[str]] = {}

    for path in PACKAGE_ROOT.rglob("*.py"):
        if path == SHIM_PATH:
            continue
        imports = _subscription_catalog_imports(path)
        if imports:
            violations[str(path.relative_to(PACKAGE_ROOT.parent))] = imports

    assert violations == {}, (
        "subscription_catalog is compatibility-only; runtime code must import "
        f"pricing_catalog directly: {violations}"
    )


def test_subscription_catalog_remains_a_thin_pricing_catalog_shim() -> None:
    tree = ast.parse(
        SHIM_PATH.read_text(encoding="utf-8"),
        filename=str(SHIM_PATH),
    )
    imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert len(imports) == 1
    only_import = imports[0]
    assert isinstance(only_import, ast.ImportFrom)
    assert only_import.module == "processual_api.billing.pricing_catalog"
