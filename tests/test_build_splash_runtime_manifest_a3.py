from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_splash_runtime_manifest.py"


def _load_compiler():
    spec = importlib.util.spec_from_file_location("build_splash_runtime_manifest", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_render_distribution_is_locked_exactly() -> None:
    compiler = _load_compiler()

    compiler.require_reference_distribution(
        Counter(compiler.EXPECTED_COLOR_FAMILY_COUNTS),
        Counter(compiler.EXPECTED_WIDTH_CLASS_COUNTS),
    )


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
