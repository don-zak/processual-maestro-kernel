#!/usr/bin/env python3
"""Resolve ownership of visually verified Splash route fragments.

Only fragments already reviewed as KEEP are considered. Ownership is inferred
from continuity evidence, never from proximity alone. Candidate route trees are
scored using endpoint adjacency, local tangent alignment, color continuity from
the approved reference, and outward progression from the central core. A fragment
is auto-assigned only when one candidate wins by a strict confidence margin;
otherwise it remains AMBIGUOUS and blocks canonical promotion.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

CORE = (608, 224, 1041, 632)
HUE_RANGES = {
    "amber": (7, 30),
    "lime": (34, 58),
    "teal": (76, 91),
    "cyan": (92, 118),
    "violet": (126, 160),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("recovered_mask", type=Path)
    parser.add_argument("reconciliation_audit", type=Path)
    parser.add_argument("partition_audit", type=Path)
    parser.add_argument("manual_closeout", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-gap", type=float, default=8.0)
    parser.add_argument("--confidence-margin", type=float, default=1.25)
    return parser.parse_args()


def color_at(hsv: np.ndarray, x: int, y: int) -> str | None:
    h, s, v = (int(value) for value in hsv[y, x])
    if s < 45 or v < 45:
        return None
    for name, (lo, hi) in HUE_RANGES.items():
        if lo <= h <= hi:
            return name
    return None


def dominant_color(hsv: np.ndarray, pixels: list[tuple[int, int]]) -> str | None:
    counts: dict[str, int] = {}
    for x, y in pixels:
        color = color_at(hsv, x, y)
        if color:
            counts[color] = counts.get(color, 0) + 1
    return max(counts, key=counts.get) if counts else None


def core_distance(x: int, y: int) -> float:
    x1, y1, x2, y2 = CORE
    dx = 0 if x1 <= x <= x2 else min(abs(x - x1), abs(x - x2))
    dy = 0 if y1 <= y <= y2 else min(abs(y - y1), abs(y - y2))
    return math.hypot(dx, dy)


def endpoints(region_pixels: set[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for x, y in region_pixels:
        degree = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                if (x + dx, y + dy) in region_pixels:
                    degree += 1
        if degree <= 1:
            result.append((x, y))
    return result or list(region_pixels)


def nearest_tree_point(
    point: tuple[int, int], tree_pixels: np.ndarray
) -> tuple[float, tuple[int, int] | None]:
    ys, xs = np.where(tree_pixels)
    if len(xs) == 0:
        return math.inf, None
    px, py = point
    distances = (xs - px) ** 2 + (ys - py) ** 2
    index = int(np.argmin(distances))
    return math.sqrt(float(distances[index])), (int(xs[index]), int(ys[index]))


def tangent(region: set[tuple[int, int]], endpoint: tuple[int, int]) -> np.ndarray | None:
    ex, ey = endpoint
    candidates = [
        (x, y) for x, y in region
        if (x, y) != endpoint and math.hypot(x - ex, y - ey) <= 6.0
    ]
    if not candidates:
        return None
    farthest = max(candidates, key=lambda point: math.hypot(point[0] - ex, point[1] - ey))
    vector = np.array([ex - farthest[0], ey - farthest[1]], dtype=float)
    norm = np.linalg.norm(vector)
    return vector / norm if norm else None


def tree_tangent(tree_pixels: np.ndarray, contact: tuple[int, int], toward: tuple[int, int]) -> np.ndarray | None:
    cx, cy = contact
    ys, xs = np.where(tree_pixels)
    candidates = [
        (int(x), int(y)) for x, y in zip(xs, ys)
        if 0 < math.hypot(int(x) - cx, int(y) - cy) <= 6.0
    ]
    if not candidates:
        return None
    tx, ty = toward
    candidate = max(
        candidates,
        key=lambda point: math.hypot(point[0] - tx, point[1] - ty),
    )
    vector = np.array([cx - candidate[0], cy - candidate[1]], dtype=float)
    norm = np.linalg.norm(vector)
    return vector / norm if norm else None


def score_candidate(
    region_pixels: set[tuple[int, int]],
    tree_pixels: np.ndarray,
    region_color: str | None,
    tree_color: str | None,
    max_gap: float,
) -> dict[str, object]:
    best_gap = math.inf
    best_endpoint: tuple[int, int] | None = None
    best_contact: tuple[int, int] | None = None
    for endpoint in endpoints(region_pixels):
        gap, contact = nearest_tree_point(endpoint, tree_pixels)
        if gap < best_gap:
            best_gap, best_endpoint, best_contact = gap, endpoint, contact

    gap_score = max(0.0, 1.0 - best_gap / max_gap) if math.isfinite(best_gap) else 0.0
    color_score = 1.0 if region_color and tree_color and region_color == tree_color else 0.0
    tangent_score = 0.0
    outward_score = 0.0
    if best_endpoint and best_contact:
        a = tangent(region_pixels, best_endpoint)
        b = tree_tangent(tree_pixels, best_contact, best_endpoint)
        if a is not None and b is not None:
            tangent_score = max(0.0, float(np.dot(a, b)))
        outward_score = 1.0 if core_distance(*best_endpoint) >= core_distance(*best_contact) else 0.0

    total = gap_score * 4.0 + tangent_score * 3.0 + color_score * 2.0 + outward_score
    return {
        "score": round(total, 4),
        "gap_px": round(best_gap, 3) if math.isfinite(best_gap) else None,
        "gap_score": round(gap_score, 4),
        "tangent_score": round(tangent_score, 4),
        "color_match": bool(color_score),
        "outward_progression": bool(outward_score),
        "endpoint": list(best_endpoint) if best_endpoint else None,
        "contact": list(best_contact) if best_contact else None,
    }


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.reference))
    mask = cv2.imread(str(args.recovered_mask), cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None:
        raise SystemExit("Reference image or recovered mask could not be read")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    skeleton = skeletonize(mask > 0)
    audit = json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    partition = json.loads(args.partition_audit.read_text(encoding="utf-8"))
    closeout = json.loads(args.manual_closeout.read_text(encoding="utf-8"))

    region_by_id = {str(region["id"]): region for region in audit.get("regions", [])}
    keep_ids = [
        str(item["region"])
        for item in closeout.get("decisions", [])
        if item.get("decision") == "KEEP"
    ]

    # Reconstruct candidate tree masks from terminal records only is insufficient;
    # partition audit must contain pixel ownership exported by the partition stage.
    tree_payload = partition.get("route_tree_pixels")
    if not isinstance(tree_payload, dict):
        raise SystemExit(
            "partition audit lacks route_tree_pixels; rerun partition_splash_reference_routes.py "
            "with pixel ownership export enabled before ownership resolution"
        )

    records: list[dict[str, object]] = []
    resolved = 0
    ambiguous = 0
    for region_id in keep_ids:
        region = region_by_id[region_id]
        pixels = {(int(x), int(y)) for x, y in region.get("pixels", [])}
        region_color = dominant_color(hsv, list(pixels))
        candidate_ids = [int(value) for value in region.get("touching_pin_labels", [])]
        scored: list[dict[str, object]] = []
        for tree_id in candidate_ids:
            tree_points = tree_payload.get(str(tree_id), [])
            tree_mask = np.zeros_like(skeleton, dtype=bool)
            for x, y in tree_points:
                tree_mask[int(y), int(x)] = True
            tree_color = dominant_color(hsv, [(int(x), int(y)) for x, y in tree_points])
            evidence = score_candidate(pixels, tree_mask, region_color, tree_color, args.max_gap)
            evidence["tree_id"] = tree_id
            evidence["tree_color"] = tree_color
            scored.append(evidence)
        scored.sort(key=lambda item: float(item["score"]), reverse=True)

        decision = "AMBIGUOUS"
        target_tree = None
        if scored:
            winner = float(scored[0]["score"])
            runner_up = float(scored[1]["score"]) if len(scored) > 1 else 0.0
            if winner >= 5.0 and winner - runner_up >= args.confidence_margin:
                decision = "ATTACH_CONTINUATION"
                target_tree = int(scored[0]["tree_id"])
                resolved += 1
            else:
                ambiguous += 1
        else:
            ambiguous += 1

        records.append({
            "region": region_id,
            "decision": decision,
            "target_tree": target_tree,
            "region_color": region_color,
            "candidate_scores": scored,
        })

    result = {
        "meta": {
            "stage": "KEPT_FRAGMENT_OWNERSHIP_RESOLUTION",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "kept_fragment_count": len(keep_ids),
            "resolved_fragment_count": resolved,
            "ambiguous_fragment_count": ambiguous,
            "resolution_policy": "unique continuity winner only; proximity alone is insufficient",
            "completion_gate": "ambiguous_fragment_count == 0",
        },
        "ownership_decisions": records,
    }
    (args.out / "ownership_resolution.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
