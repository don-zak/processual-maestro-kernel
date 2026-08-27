#!/usr/bin/env python3
"""Compile the canonical Splash graph and reference-derived render semantics.

This is a strict, topology-preserving compiler. It never generates, extends,
smooths, interpolates, or otherwise changes route geometry. It joins the exact
canonical graph edge paths with their audited color-family and width-class
semantics and emits a browser-consumable manifest.

The compiler deliberately fails closed when the canonical artifacts are
incomplete or disagree. This keeps the final Splash renderer from silently
falling back to procedural or hand-authored routing.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Iterable

REFERENCE_SIZE = [1672, 941]
REFERENCE_CORE_BOUNDS = [608, 224, 1041, 632]
EXPECTED_ROUTE_TREES = 125
EXPECTED_EDGES = 5496
REQUIRED_COLOR_FAMILIES = {"amber", "lime", "teal", "cyan", "violet"}
REQUIRED_WIDTH_CLASSES = {"thin", "thick"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical_graph", type=Path)
    parser.add_argument("render_semantics", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def iter_graph_edges(graph: dict[str, object]) -> Iterable[tuple[str, str, dict[str, object]]]:
    for tree in graph.get("route_trees", []):
        assert isinstance(tree, dict)
        for edge in tree.get("edges", []):
            assert isinstance(edge, dict)
            yield "tree", str(tree["tree_id"]), edge
    for group in ("shared_geometry", "preserved_unowned_geometry"):
        for record in graph.get(group, []):
            assert isinstance(record, dict)
            for edge in record.get("edges", []):
                assert isinstance(edge, dict)
                yield group, str(record.get("id", "")), edge


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def compile_manifest(graph: dict[str, object], semantics: dict[str, object]) -> dict[str, object]:
    graph_meta = graph.get("meta", {})
    require(isinstance(graph_meta, dict), "Canonical graph meta must be an object")
    require(
        int(graph_meta.get("route_tree_count", 0)) == EXPECTED_ROUTE_TREES,
        f"Canonical graph must contain exactly {EXPECTED_ROUTE_TREES} route trees",
    )
    require(
        int(graph_meta.get("unrepresented_tree_count", 1)) == 0,
        "Canonical graph still contains unrepresented route-tree pixels",
    )

    semantic_meta = semantics.get("meta", {})
    require(isinstance(semantic_meta, dict), "Render semantics meta must be an object")
    require(
        bool(semantic_meta.get("edge_color_assignment_complete")),
        "Render semantics are missing one or more color assignments",
    )
    require(
        bool(semantic_meta.get("edge_width_assignment_complete")),
        "Render semantics are missing one or more width assignments",
    )
    require(
        int(semantic_meta.get("zero_color_support_edge_count", 1)) == 0,
        "At least one edge has no reference-backed color support",
    )

    semantic_records = semantics.get("edges", [])
    require(isinstance(semantic_records, list), "Render semantics edges must be a list")
    semantics_by_id: dict[str, dict[str, object]] = {}
    for record in semantic_records:
        require(isinstance(record, dict), "Invalid render semantics edge record")
        edge_id = str(record.get("edge_id", ""))
        require(bool(edge_id), "Render semantics edge is missing edge_id")
        require(edge_id not in semantics_by_id, f"Duplicate semantic edge_id: {edge_id}")
        semantics_by_id[edge_id] = record

    compiled_edges: list[dict[str, object]] = []
    graph_edge_ids: set[str] = set()
    for kind, parent_id, edge in iter_graph_edges(graph):
        edge_id = str(edge.get("edge_id", ""))
        require(bool(edge_id), "Canonical graph edge is missing edge_id")
        require(edge_id not in graph_edge_ids, f"Duplicate canonical graph edge_id: {edge_id}")
        graph_edge_ids.add(edge_id)
        semantic = semantics_by_id.get(edge_id)
        require(semantic is not None, f"Missing render semantics for canonical edge: {edge_id}")

        path = edge.get("path", [])
        require(isinstance(path, list) and len(path) > 0, f"Empty canonical path: {edge_id}")
        normalized_path: list[list[int]] = []
        for point in path:
            require(
                isinstance(point, list) and len(point) == 2,
                f"Invalid canonical point in {edge_id}",
            )
            x, y = int(point[0]), int(point[1])
            require(0 <= x < REFERENCE_SIZE[0] and 0 <= y < REFERENCE_SIZE[1], f"Out-of-bounds point in {edge_id}")
            normalized_path.append([x, y])

        color_family = str(semantic.get("color_family", ""))
        width_class = str(semantic.get("width_class", ""))
        require(color_family in REQUIRED_COLOR_FAMILIES, f"Invalid color family for {edge_id}: {color_family}")
        require(width_class in REQUIRED_WIDTH_CLASSES, f"Invalid width class for {edge_id}: {width_class}")

        compiled_edges.append(
            {
                "edge_id": edge_id,
                "kind": kind,
                "parent_id": parent_id,
                "path": normalized_path,
                "pixel_count": len(normalized_path),
                "color_family": color_family,
                "width_class": width_class,
                "measured_support_span_px": float(semantic.get("measured_support_span_px", 0.0)),
            }
        )

    require(graph_edge_ids == set(semantics_by_id), "Canonical graph and render semantics edge IDs are not a bijection")
    require(len(compiled_edges) == EXPECTED_EDGES, f"Expected {EXPECTED_EDGES} canonical edges, got {len(compiled_edges)}")

    colors = Counter(str(edge["color_family"]) for edge in compiled_edges)
    widths = Counter(str(edge["width_class"]) for edge in compiled_edges)
    require(set(colors) == REQUIRED_COLOR_FAMILIES, "Runtime manifest is missing one or more required color families")
    require(set(widths) == REQUIRED_WIDTH_CLASSES, "Runtime manifest must contain exactly thin and thick width classes")

    route_trees = []
    for tree in graph.get("route_trees", []):
        assert isinstance(tree, dict)
        route_trees.append(
            {
                "tree_id": int(tree["tree_id"]),
                "pin_id": tree.get("pin_id"),
                "side": tree.get("side"),
                "pin": tree.get("pin"),
                "seed": tree.get("seed"),
                "terminals": tree.get("terminals", []),
                "junctions": tree.get("junctions", []),
                "isolated_nodes": tree.get("isolated_nodes", []),
            }
        )

    return {
        "meta": {
            "contract_version": "A3-splash-runtime-render-v1",
            "source_of_truth": "approved pivot reference image via canonical graph + audited render semantics",
            "reference_size": REFERENCE_SIZE,
            "reference_core_bounds": REFERENCE_CORE_BOUNDS,
            "route_tree_count": len(route_trees),
            "edge_count": len(compiled_edges),
            "color_family_counts": dict(colors),
            "width_class_counts": dict(widths),
            "synthetic_geometry_pixels": 0,
            "procedural_generation_allowed": False,
            "hand_authored_route_extension_allowed": False,
            "canonical_geometry_modified": False,
            "renderer_ready": True,
            "visual_acceptance_passed": False,
        },
        "route_trees": route_trees,
        "edges": compiled_edges,
    }


def main() -> None:
    args = parse_args()
    graph = json.loads(args.canonical_graph.read_text(encoding="utf-8"))
    semantics = json.loads(args.render_semantics.read_text(encoding="utf-8"))
    result = compile_manifest(graph, semantics)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
