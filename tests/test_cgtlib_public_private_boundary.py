from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from cgtlib import _fallback
from cgtlib._backend import HAS_PRIVATE_COMPUTE


PUBLIC_CGTLIB = Path(__file__).resolve().parents[1] / "cgtlib"
BACKEND_RESOLVER = PUBLIC_CGTLIB / "_backend.py"
PUBLIC_WRAPPERS = (
    "cgtlib.aftermath",
    "cgtlib.compatibility",
    "cgtlib.evaluators",
    "cgtlib.existence",
    "cgtlib.fate",
    "cgtlib.gates",
    "cgtlib.lift",
    "cgtlib.locking",
    "cgtlib.phase",
    "cgtlib.possibility",
    "cgtlib.retention",
)


def _private_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("cgtlib.private") or (node.level and module.startswith("private")):
                findings.append(f"{path.name}:{node.lineno}:{module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("cgtlib.private"):
                    findings.append(f"{path.name}:{node.lineno}:{alias.name}")
    return findings


def test_only_backend_resolver_may_import_private_cgt() -> None:
    offenders: list[str] = []
    for path in sorted(PUBLIC_CGTLIB.rglob("*.py")):
        if path == BACKEND_RESOLVER or "private" in path.parts:
            continue
        offenders.extend(_private_imports(path))
    assert offenders == []


def test_public_cgt_wrappers_import_without_private_engine() -> None:
    for module_name in PUBLIC_WRAPPERS:
        importlib.import_module(module_name)


def test_public_build_fails_closed_for_private_only_computation() -> None:
    if HAS_PRIVATE_COMPUTE:
        pytest.skip("private CGT engine is present in this checkout")

    gates = importlib.import_module("cgtlib.gates")
    fate = importlib.import_module("cgtlib.fate")

    with pytest.raises(_fallback._FeatureUnavailableError, match="private CGT engine"):
        gates.compute_delay_gate(1.0, 1.0, 1.0)
    with pytest.raises(_fallback._FeatureUnavailableError, match="private CGT engine"):
        fate.compute_repeatability(0.5, 0.5, 0.5, 0.5)
