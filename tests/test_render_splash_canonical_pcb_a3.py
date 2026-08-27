from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_splash_canonical_pcb.py"


def _load_renderer():
    spec = importlib.util.spec_from_file_location("render_splash_canonical_pcb", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _graph() -> dict:
    trees = []
    for tree_id in range(1, 126):
        edges = []
        if tree_id == 1:
            edges.append(
                {
                    "edge_id": "tree-001-edge-001",
                    "path": [[10, 10], [11, 10], [12, 11], [13, 11]],
                }
            )
        elif tree_id == 2:
            edges.append(
                {
                    "edge_id": "tree-002-edge-001",
                    "path": [[100, 100], [100, 101], [101, 102]],
                }
            )
        trees.append({"tree_id": tree_id, "edges": edges})
    return {
        "meta": {"route_tree_count": 125, "unrepresented_tree_count": 0},
        "route_trees": trees,
        "shared_geometry": [],
        "preserved_unowned_geometry": [],
    }


def _semantics() -> dict:
    return {
        "edges": [
            {
                "edge_id": "tree-001-edge-001",
                "color_family": "cyan",
                "width_class": "thin",
            },
            {
                "edge_id": "tree-002-edge-001",
                "color_family": "amber",
                "width_class": "thick",
            },
        ]
    }


def test_renderer_emits_exact_ordered_pixel_paths_without_geometry_transform(tmp_path: Path) -> None:
    renderer = _load_renderer()
    paths, semantics = renderer.validate(_graph(), _semantics())

    cyan = renderer.render_family("cyan", paths, semantics)
    amber = renderer.render_family("amber", paths, semantics)

    assert 'points="10,10 11,10 12,11 13,11"' in cyan
    assert 'points="100,100 100,101 101,102"' in amber
    assert 'data-width-class="thin"' in cyan
    assert 'data-width-class="thick"' in amber
    assert 'stroke-width="1.25"' in cyan
    assert 'stroke-width="2.6"' in amber
    assert 'vector-effect="non-scaling-stroke"' in cyan
    assert " C" not in cyan
    assert " Q" not in cyan


def test_renderer_rejects_graph_semantics_edge_mismatch() -> None:
    renderer = _load_renderer()
    broken = _semantics()
    broken["edges"].pop()

    with pytest.raises(SystemExit, match="Graph/semantics edge mismatch"):
        renderer.validate(_graph(), broken)


def test_renderer_contract_declares_geometry_passive_output(tmp_path: Path) -> None:
    renderer = _load_renderer()
    graph_path = tmp_path / "graph.json"
    semantics_path = tmp_path / "semantics.json"
    graph_path.write_text(json.dumps(_graph()), encoding="utf-8")
    semantics_path.write_text(json.dumps(_semantics()), encoding="utf-8")

    paths, semantics = renderer.validate(_graph(), _semantics())
    for family in renderer.FAMILIES:
        (tmp_path / f"splash_routes_{family}.svg").write_text(
            renderer.render_family(family, paths, semantics), encoding="utf-8"
        )

    assert (tmp_path / "splash_routes_cyan.svg").is_file()
    assert (tmp_path / "splash_routes_amber.svg").is_file()
