#!/usr/bin/env python3
"""Render canonical Splash graph edges as clean PCB-style SVG strokes.

The renderer is deliberately geometry-passive: every SVG polyline is emitted
from the exact ordered pixel path already present in the promoted canonical
graph. It never interpolates, smooths, simplifies, shifts, extends, or invents
route geometry. Color family and width class come only from the promoted
reference-derived render semantics.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

STAGE_WIDTH = 1672
STAGE_HEIGHT = 941
FAMILIES = ("cyan", "teal", "lime", "amber", "violet")
COLORS = {
    "cyan": "#16d9ff",
    "teal": "#18f5e9",
    "lime": "#a6ff43",
    "amber": "#ffad1f",
    "violet": "#d36cff",
}
# Presentation widths only. They preserve exactly two semantic classes; the
# measured support cluster centers are evidence, not literal CSS stroke widths.
STROKE_WIDTHS = {"thin": 1.25, "thick": 2.6}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical_graph", type=Path)
    parser.add_argument("render_semantics", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def graph_edges(graph: dict) -> dict[str, list[list[int]]]:
    result: dict[str, list[list[int]]] = {}
    for tree in graph.get("route_trees", []):
        for edge in tree.get("edges", []):
            result[str(edge["edge_id"])] = edge["path"]
    for group_name in ("shared_geometry", "preserved_unowned_geometry"):
        for group in graph.get(group_name, []):
            for edge in group.get("edges", []):
                result[str(edge["edge_id"])] = edge["path"]
    return result


def validate(graph: dict, semantics: dict) -> tuple[dict[str, list[list[int]]], dict[str, dict]]:
    meta = graph.get("meta", {})
    if int(meta.get("route_tree_count", 0)) != 125:
        raise SystemExit("Canonical graph must contain exactly 125 route trees")
    if int(meta.get("unrepresented_tree_count", 1)) != 0:
        raise SystemExit("Canonical graph still has unrepresented route-tree pixels")

    edge_paths = graph_edges(graph)
    semantic_records = {str(item["edge_id"]): item for item in semantics.get("edges", [])}
    if not edge_paths:
        raise SystemExit("Canonical graph contains no renderable edges")
    if set(edge_paths) != set(semantic_records):
        missing_semantics = sorted(set(edge_paths) - set(semantic_records))
        missing_geometry = sorted(set(semantic_records) - set(edge_paths))
        raise SystemExit(
            "Graph/semantics edge mismatch: "
            f"missing_semantics={missing_semantics[:5]} "
            f"missing_geometry={missing_geometry[:5]}"
        )

    for edge_id, path in edge_paths.items():
        if not path:
            raise SystemExit(f"Empty path: {edge_id}")
        for point in path:
            if len(point) != 2:
                raise SystemExit(f"Malformed point in {edge_id}: {point}")
            x, y = int(point[0]), int(point[1])
            if not (0 <= x < STAGE_WIDTH and 0 <= y < STAGE_HEIGHT):
                raise SystemExit(f"Out-of-bounds canonical point in {edge_id}: {(x, y)}")
        record = semantic_records[edge_id]
        if record.get("color_family") not in FAMILIES:
            raise SystemExit(f"Unsupported color family for {edge_id}")
        if record.get("width_class") not in STROKE_WIDTHS:
            raise SystemExit(f"Unsupported width class for {edge_id}")
    return edge_paths, semantic_records


def polyline(edge_id: str, path: list[list[int]], record: dict) -> str:
    family = str(record["color_family"])
    width_class = str(record["width_class"])
    points = " ".join(f"{int(x)},{int(y)}" for x, y in path)
    return (
        f'<polyline id="{escape(edge_id)}" data-canonical-edge="true" '
        f'data-width-class="{width_class}" points="{points}" '
        f'fill="none" stroke="{COLORS[family]}" stroke-width="{STROKE_WIDTHS[width_class]}" '
        'stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>'
    )


def render_family(family: str, edge_paths: dict[str, list[list[int]]], semantics: dict[str, dict]) -> str:
    selected = [
        edge_id for edge_id in edge_paths
        if semantics[edge_id]["color_family"] == family
    ]
    body = "\n".join(polyline(edge_id, edge_paths[edge_id], semantics[edge_id]) for edge_id in selected)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {STAGE_WIDTH} {STAGE_HEIGHT}" '
        f'width="{STAGE_WIDTH}" height="{STAGE_HEIGHT}" role="img" '
        f'aria-label="Maestro canonical PCB {family} routes">\n'
        f'<g class="route {family}" data-canonical-family="{family}">\n{body}\n</g>\n</svg>\n'
    )


def main() -> None:
    args = parse_args()
    graph = json.loads(args.canonical_graph.read_text(encoding="utf-8"))
    semantics_doc = json.loads(args.render_semantics.read_text(encoding="utf-8"))
    edge_paths, semantic_records = validate(graph, semantics_doc)

    args.out.mkdir(parents=True, exist_ok=True)
    counts = Counter(record["color_family"] for record in semantic_records.values())
    widths = Counter(record["width_class"] for record in semantic_records.values())

    for family in FAMILIES:
        target = args.out / f"splash_routes_{family}.svg"
        target.write_text(render_family(family, edge_paths, semantic_records), encoding="utf-8")

    evidence = {
        "stage": [STAGE_WIDTH, STAGE_HEIGHT],
        "edge_count": len(edge_paths),
        "color_family_counts": dict(counts),
        "width_class_counts": dict(widths),
        "coordinate_transform": "none",
        "geometry_modified": False,
        "smoothing": False,
        "interpolation": False,
        "synthetic_geometry": False,
        "renderer": "canonical-ordered-pixel-polyline-v1",
    }
    (args.out / "canonical_pcb_render_evidence.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
