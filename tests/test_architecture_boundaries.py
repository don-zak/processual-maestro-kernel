from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _imports_package(path: Path, forbidden_root: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] == forbidden_root for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".", 1)[0] == forbidden_root:
                return True
    return False


def _violations(package_root: str, forbidden_root: str) -> list[str]:
    root = REPO_ROOT / package_root
    return [
        path.relative_to(REPO_ROOT).as_posix()
        for path in sorted(root.rglob("*.py"))
        if _imports_package(path, forbidden_root)
    ]


def test_processual_kernel_does_not_depend_on_processual_api() -> None:
    assert _violations("processual_kernel", "processual_api") == []


def test_cgtlib_does_not_depend_on_processual_api() -> None:
    assert _violations("cgtlib", "processual_api") == []
