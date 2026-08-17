from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "processual_api"
TESTS_ROOT = REPO_ROOT / "tests"
SHIM_PATH = PACKAGE_ROOT / "billing" / "subscription_catalog.py"
ALLOWED_TEST_CONSUMERS = {
    Path("tests/test_subscription_pricing_catalog.py"),
}


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
            violations[str(path.relative_to(REPO_ROOT))] = imports

    assert violations == {}, (
        "subscription_catalog is compatibility-only; runtime code must import "
        f"pricing_catalog directly: {violations}"
    )


def test_subscription_catalog_repo_consumers_are_explicitly_allowlisted() -> None:
    consumers: set[Path] = set()

    for path in TESTS_ROOT.rglob("*.py"):
        if _subscription_catalog_imports(path):
            consumers.add(path.relative_to(REPO_ROOT))

    assert consumers == ALLOWED_TEST_CONSUMERS, (
        "Update the legacy-consumer inventory intentionally before adding or "
        "removing a subscription_catalog compatibility consumer: "
        f"expected={sorted(map(str, ALLOWED_TEST_CONSUMERS))}, "
        f"actual={sorted(map(str, consumers))}"
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
