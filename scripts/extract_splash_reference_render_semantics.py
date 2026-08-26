#!/usr/bin/env python3
"""Extract reference-derived color and width semantics for canonical Splash edges.

Geometry must already be canonical. This stage samples only the approved
reference image around each exact graph path; it never changes coordinates.
Color is assigned from the measured HSV family with strongest local support.
Width is measured as a local perpendicular high-chroma support span and clustered
into exactly two classes (thin/thick). The measured support span is preserved so
a renderer can calibrate stroke/glow separately without inventing topology.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

HUE_RANGES = {
    "amber": (7, 30),
    "lime": (34, 58),
    "teal": (76, 91),
    "cyan": (92, 118),
    "violet": (126, 160),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("reference", type=Path)
    p.add_argument("canonical_graph", type=Path)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def family_for_hue(value: int) -> str | None:
    for family, (low, high) in HUE_RANGES.items():
        if low <= value <= high:
            return family
    return None


def color_family(hue, saturation, value, path, radius: int = 3):
    scores = {family: 0.0 for family in HUE_RANGES}
    h, w = hue.shape
    step = max(1, len(path) // 80)
    for x, y in path[::step]:
        for yy in range(max(0, y - radius), min(h, y + radius + 1)):
            for xx in range(max(0, x - radius), min(w, x + radius + 1)):
                family = family_for_hue(int(hue[yy, xx]))
                sat = int(saturation[yy, xx])
                val = int(value[yy, xx])
                if family is None or sat < 35 or val < 30:
                    continue
                distance = math.hypot(xx - x, yy - y)
                scores[family] += (sat / 255.0) * (val / 255.0) / (1.0 + distance)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    winner, winner_score = ordered[0]
    runner_up = ordered[1][1]
    total = sum(scores.values())
    dominance = winner_score / total if total else 0.0
    margin = (winner_score - runner_up) / winner_score if winner_score else 0.0
    return winner, winner_score, dominance, margin


def family_masks(hue, saturation, value):
    masks = {}
    bright = ((value >= 105) & (saturation <= 110)).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    for family, (low, high) in HUE_RANGES.items():
        chroma = (
            (hue >= low)
            & (hue <= high)
            & (saturation >= 75)
            & (value >= 45)
        ).astype(np.uint8)
        nearby = cv2.dilate(chroma, kernel, iterations=1)
        masks[family] = ((chroma > 0) | ((bright > 0) & (nearby > 0))).astype(np.uint8)
    return masks


def local_width(mask: np.ndarray, path: list[tuple[int, int]]) -> float:
    if not path:
        return 1.0
    values: list[int] = []
    count = len(path)
    step = max(1, count // 100)
    for index in range(0, count, step):
        x, y = path[index]
        left = max(0, index - 2)
        right = min(count - 1, index + 2)
        dx = path[right][0] - path[left][0]
        dy = path[right][1] - path[left][1]
        if dx == 0 and dy == 0:
            continue
        if abs(dx) >= 2 * abs(dy):
            px, py = 0, 1
        elif abs(dy) >= 2 * abs(dx):
            px, py = 1, 0
        elif dx * dy >= 0:
            px, py = 1, -1
        else:
            px, py = 1, 1
        offsets = []
        for offset in range(-6, 7):
            xx, yy = x + offset * px, y + offset * py
            if 0 <= yy < mask.shape[0] and 0 <= xx < mask.shape[1] and mask[yy, xx]:
                offsets.append(offset)
        if not offsets:
            continue
        intervals = []
        start = previous = offsets[0]
        for offset in offsets[1:]:
            if offset == previous + 1:
                previous = offset
            else:
                intervals.append((start, previous))
                start = previous = offset
        intervals.append((start, previous))
        chosen = min(
            intervals,
            key=lambda interval: 0
            if interval[0] <= 0 <= interval[1]
            else min(abs(interval[0]), abs(interval[1])),
        )
        values.append(chosen[1] - chosen[0] + 1)
    return float(np.median(values)) if values else 1.0


def kmeans_two(values: list[float]) -> tuple[np.ndarray, list[float]]:
    data = np.asarray(values, dtype=float)
    centers = np.percentile(data, [30, 75]).astype(float)
    labels = np.zeros(len(data), dtype=int)
    for _ in range(40):
        labels = np.argmin(np.abs(data[:, None] - centers[None, :]), axis=1)
        updated = np.array([
            data[labels == i].mean() if np.any(labels == i) else centers[i]
            for i in range(2)
        ])
        if np.allclose(updated, centers):
            break
        centers = updated
    order = np.argsort(centers)
    remap = {int(order[0]): 0, int(order[1]): 1}
    labels = np.array([remap[int(label)] for label in labels])
    return labels, [float(centers[order[0]]), float(centers[order[1]])]


def edges(graph):
    for tree in graph.get("route_trees", []):
        for edge in tree.get("edges", []):
            yield "tree", str(tree["tree_id"]), edge
    for group in ("shared_geometry", "preserved_unowned_geometry"):
        for item in graph.get(group, []):
            for edge in item.get("edges", []):
                yield group, str(item.get("id")), edge


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.reference))
    if image is None:
        raise SystemExit(f"Cannot read approved reference: {args.reference}")
    graph = json.loads(args.canonical_graph.read_text(encoding="utf-8"))
    if int(graph.get("meta", {}).get("route_tree_count", 0)) != 125:
        raise SystemExit("Canonical graph does not contain exactly 125 route trees")
    if int(graph.get("meta", {}).get("unrepresented_tree_count", 1)) != 0:
        raise SystemExit("Canonical graph still has unrepresented route-tree pixels")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    masks = family_masks(hue, saturation, value)
    records = []
    width_values = []
    zero_support = []
    low_dominance = []

    for kind, parent_id, edge in edges(graph):
        path = [(int(x), int(y)) for x, y in edge.get("path", [])]
        if not path:
            raise SystemExit(f"Empty canonical graph edge: {edge.get('edge_id')}")
        family, support, dominance, margin = color_family(hue, saturation, value, path)
        width = local_width(masks[family], path)
        record = {
            "edge_id": edge["edge_id"],
            "kind": kind,
            "parent_id": parent_id,
            "pixel_count": len(path),
            "color_family": family,
            "color_support_score": round(float(support), 4),
            "color_dominance_ratio": round(float(dominance), 4),
            "color_margin_ratio": round(float(margin), 4),
            "measured_support_span_px": round(float(width), 3),
        }
        records.append(record)
        width_values.append(width)
        if support <= 0:
            zero_support.append(edge["edge_id"])
        if dominance < 0.55:
            low_dominance.append(edge["edge_id"])

    labels, centers = kmeans_two(width_values)
    for record, label in zip(records, labels):
        record["width_class"] = "thin" if int(label) == 0 else "thick"

    metadata = {
        "stage": "REFERENCE_DERIVED_RENDER_SEMANTICS_AUDIT",
        "edge_count": len(records),
        "color_family_counts": dict(Counter(r["color_family"] for r in records)),
        "width_class_counts": dict(Counter(r["width_class"] for r in records)),
        "width_cluster_centers_measured_support_px": [round(v, 3) for v in centers],
        "zero_color_support_edge_count": len(zero_support),
        "low_color_dominance_edge_count": len(low_dominance),
        "edge_color_assignment_complete": len(zero_support) == 0,
        "edge_width_assignment_complete": len(records) > 0,
        "geometry_modified": False,
        "canonical_render_manifest_ready": False,
        "splash_reconstruction_allowed": False,
        "next_gate": "review low-dominance color edges, then promote canonical render manifest",
    }
    result = {
        "meta": metadata,
        "edges": records,
        "zero_color_support_edges": zero_support,
        "low_color_dominance_edges": low_dominance,
    }
    (args.out / "reference_render_semantics_audit.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))
    if zero_support:
        raise SystemExit("Some canonical edges have no defensible reference color support")


if __name__ == "__main__":
    main()
