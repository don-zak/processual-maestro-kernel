from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_splash_runtime_manifest.py"
CANONICAL_RENDER_CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_canonical_render_manifest_a3.json"


def _load_compiler():
    spec = importlib.util.spec_from_file_location("build_splash_runtime_manifest", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_render_contract() -> dict[str, object]:
    return json.loads(CANONICAL_RENDER_CONTRACT.read_text(encoding="utf-8"))


def test_reference_render_distribution_is_locked_exactly() -> None:
    compiler = _load_compiler()

    compiler.require_reference_distribution(
        Counter(compiler.EXPECTED_COLOR_FAMILY_COUNTS),
        Counter(compiler.EXPECTED_WIDTH_CLASS_COUNTS),
    )


def test_compiler_distribution_constants_match_promoted_canonical_contract() -> None:
    compiler = _load_compiler()
    contract = _canonical_render_contract()
    geometry = contract["geometry"]
    semantics = contract["render_semantics"]

    assert contract["source_of_truth"] == "approved 1672x941 pivot reference"
    assert geometry["route_tree_count"] == compiler.EXPECTED_ROUTE_TREES
    assert geometry["synthetic_geometry_pixels"] == 0
    assert semantics["edge_count"] == compiler.EXPECTED_EDGES
    assert semantics["color_family_counts"] == compiler.EXPECTED_COLOR_FAMILY_COUNTS
    assert semantics["width_class_counts"] == compiler.EXPECTED_WIDTH_CLASS_COUNTS
    assert semantics["zero_color_support_edge_count"] == 0
    assert semantics["edge_color_assignment_complete"] is True
    assert semantics["edge_width_assignment_complete"] is True


def test_color_drift_fails_closed_even_when_total_edge_count_is_unchanged() -> None:
    compiler = _load_compiler()
    colors = Counter(compiler.EXPECTED_COLOR_FAMILY_COUNTS)
    colors["cyan"] -= 1
    colors["amber"] += 1

    assert sum(colors.values()) == compiler.EXPECTED_EDGES
    with pytest.raises(SystemExit, match="Canonical color-family distribution mismatch"):
        compiler.require_reference_distribution(
            colors,
            Counter(compiler.EXPECTED_WIDTH_CLASS_COUNTS),
        )


def test_width_drift_fails_closed_even_when_total_edge_count_is_unchanged() -> None:
    compiler = _load_compiler()
    widths = Counter(compiler.EXPECTED_WIDTH_CLASS_COUNTS)
    widths["thin"] -= 1
    widths["thick"] += 1

    assert sum(widths.values()) == compiler.EXPECTED_EDGES
    with pytest.raises(SystemExit, match="Canonical width-class distribution mismatch"):
        compiler.require_reference_distribution(
            Counter(compiler.EXPECTED_COLOR_FAMILY_COUNTS),
            widths,
        )


def test_locked_distributions_cover_every_canonical_edge() -> None:
    compiler = _load_compiler()

    assert sum(compiler.EXPECTED_COLOR_FAMILY_COUNTS.values()) == compiler.EXPECTED_EDGES
    assert sum(compiler.EXPECTED_WIDTH_CLASS_COUNTS.values()) == compiler.EXPECTED_EDGES
    assert set(compiler.EXPECTED_COLOR_FAMILY_COUNTS) == compiler.REQUIRED_COLOR_FAMILIES
    assert set(compiler.EXPECTED_WIDTH_CLASS_COUNTS) == compiler.REQUIRED_WIDTH_CLASSES
