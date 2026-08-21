from __future__ import annotations

from pathlib import Path


PUBLIC_SOURCE_ROOTS = (
    Path("processual_api"),
    Path("processual_kernel"),
    Path("cgtlib"),
)

FORBIDDEN_PRIVATE_PATHS = (
    Path("cgtlib/private"),
    Path("processual_api/private_integrations"),
)

FORBIDDEN_PRIVATE_IMPORT_TOKENS = (
    "cgtlib.private",
    "processual_api.private_integrations",
    ".private_integrations",
)


def test_private_source_trees_are_absent_from_public_repository() -> None:
    for path in FORBIDDEN_PRIVATE_PATHS:
        assert not path.exists(), f"private source tree must not exist in public repository: {path}"


def test_public_runtime_sources_do_not_import_private_implementation_modules() -> None:
    violations: list[str] = []
    for root in PUBLIC_SOURCE_ROOTS:
        for path in root.rglob("*.py"):
            text = path.read_text("utf-8")
            for token in FORBIDDEN_PRIVATE_IMPORT_TOKENS:
                if token in text:
                    violations.append(f"{path}: {token}")

    assert violations == []


def test_public_boundary_contract_contains_no_private_module_locator_logic() -> None:
    boundary = Path("processual_api/integrations/private_evaluation_boundary.py").read_text("utf-8")
    forbidden = (
        "find_spec(",
        "import_module(",
        "__import__(",
        "private_integrations",
        "cgtlib.private",
    )
    for token in forbidden:
        assert token not in boundary
