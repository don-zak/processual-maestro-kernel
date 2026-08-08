from __future__ import annotations

import ast
from pathlib import Path


RUNTIME_ROOT = Path("processual_api")


def _benchmark_imports(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "benchmarks" or alias.name.startswith("benchmarks."):
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "benchmarks" or module.startswith("benchmarks."):
                violations.append(module)
    return violations


def test_runtime_package_does_not_import_benchmark_modules() -> None:
    violations: list[str] = []
    for path in sorted(RUNTIME_ROOT.rglob("*.py")):
        for module in _benchmark_imports(path):
            violations.append(f"{path}: {module}")

    assert violations == [], (
        "benchmark/soak code must remain CI-only and outside runtime imports: "
        + ", ".join(violations)
    )
