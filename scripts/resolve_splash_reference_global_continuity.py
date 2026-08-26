#!/usr/bin/env python3
"""Resolve ambiguous kept route fragments using global path continuity.

This second-pass resolver consumes local ownership scores and evaluates a wider
path neighborhood. It uses long-axis alignment, support from both fragment
endpoints, and radial progression away from the central core. It never adds
pixels. A fragment is assigned only when a candidate clears both an absolute
score and a winner margin; otherwise it stays AMBIGUOUS and blocks canonical
promotion.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np

CORE = (608, 224, 1041, 632)
NEIGHBOURS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),             (0, 1),
    (1, -1),  (1, 0),    (1, 1),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reconciliation_audit", type=Path)
    parser.add_argument("partition_audit", type=Path)
    parser.add_argument("local_ownership", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--axis-radius", type=float, default=36.0)
    parser.add_argument("--endpoint-gap", type=float, default=12.0)
    parser.add_argument("--score-min", type=float, default=6.0)
    parser.add_argument("--winner-margin", type=float, default=1.0)
    return parser.parse_args()


def core_distance(x: int, y: int) -> float:
    x1, y1, x2, y2 = CORE
    dx = 0 if x1 <= x <= x2 else min(abs(x - x1), abs(x - x2))
    dy = 0 if y1 <= y <= y2 else min(abs(y - y1), abs(y - y2))
    return math.hypot(dx, dy)


def endpoints(region: set[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for x, y in region:
        degree = sum((x + dx, y + dy) in region for dy, dx in NEIGHBOURS)
        if degree <= 1:
            result.append((x, y))
    return result or list(region)


def fit_axis(points: list[tuple[int, int]]) -> tuple[np.ndarray, np.ndarray] | None:
    if len(points) < 2:
        return None
    values = np.array(points, dtype=float)
    center = values.mean(axis=0)
    _, _, vectors = np.linalg.svd(values - center, full_matrices=False)
    return center, vectors[0]


def axis_alignment(
    a: tuple[np.ndarray, np.ndarray] | None,
    b: tuple[np.ndarray, np.ndarray] | None,
) -> float:
    if a is None or b is None:
        return 0.0
    return abs(float(np.dot(a[1], b[1])))


def nearest_tree_point(point: tuple[int, int], tree: set[tuple[int, int]]) -> tuple[float, tuple[int, int] | None]:
    if not tree:
        return math.inf, None
    px, py = point
    candidate = min(tree, key=lambda p: (p[0] - px) ** 2 + (p[1] - py) ** 2)
    return math.hypot(candidate[0] - px, candidate[1] - py), candidate


def local_tree_axis(
    tree: set[tuple[int, int]],
    contact: tuple[int, int],
    radius: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    cx, cy = contact
    points = [p for p in tree if math.hypot(p[0] - cx, p[1] - cy) <= radius]
    return fit_axis(points)


def score_candidate(
    region: set[tuple[int, int]],
    tree: set[tuple[int, int]],
    base_score: float,
    axis_radius: float,
    endpoint_gap: float,
) -> dict[str, object]:
    pairs: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
    for endpoint in endpoints(region):
        gap, contact = nearest_tree_point(endpoint, tree)
        if contact is not None and gap <= endpoint_gap:
            pairs.append((gap, endpoint, contact))
    pairs.sort(key=lambda item: item[0])

    long_axis = 0.0
    dual_endpoint = False
    radial_progress = 0.0
    if pairs:
        _, endpoint, contact = pairs[0]
        long_axis = axis_alignment(fit_axis(list(region)), local_tree_axis(tree, contact, axis_radius))
        dual_endpoint = len(pairs) >= 2 and pairs[1][0] <= endpoint_gap
        radial_progress = max(
            0.0,
            min(1.0, (core_distance(*endpoint) - core_distance(*contact)) / 20.0),
        )

    total = base_score + long_axis * 3.0 + (2.0 if dual_endpoint else 0.0) + radial_progress * 1.5
    return {
        "score": round(total, 4),
        "base_score": round(base_score, 4),
        "long_axis_alignment": round(long_axis, 4),
        "dual_endpoint_support": dual_endpoint,
        "radial_progress": round(radial_progress, 4),
        "nearest_gap_px": round(pairs[0][0], 3) if pairs else None,
    }


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    audit = json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    partition = json.loads(args.partition_audit.read_text(encoding="utf-8"))
    local = json.loads(args.local_ownership.read_text(encoding="utf-8"))
    regions = {str(item["id"]): item for item in audit.get("regions", [])}
    tree_payload = partition.get("route_tree_pixels")
    if not isinstance(tree_payload, dict):
        raise SystemExit("partition audit lacks route_tree_pixels")

    records: list[dict[str, object]] = []
    resolved = 0
    ambiguous = 0
    for item in local.get("ownership_decisions", []):
        if item.get("decision") != "AMBIGUOUS":
            continue
        region_id = str(item["region"])
        region = {(int(x), int(y)) for x, y in regions[region_id].get("pixels", [])}
        scored: list[dict[str, object]] = []
        for candidate in item.get("candidate_scores", []):
            tree_id = int(candidate["tree_id"])
            tree = {(int(x), int(y)) for x, y in tree_payload.get(str(tree_id), [])}
            evidence = score_candidate(
                region,
                tree,
                float(candidate["score"]),
                args.axis_radius,
                args.endpoint_gap,
            )
            evidence["tree_id"] = tree_id
            scored.append(evidence)
        scored.sort(key=lambda row: float(row["score"]), reverse=True)

        decision = "AMBIGUOUS"
        target_tree = None
        margin = None
        if scored:
            winner = float(scored[0]["score"])
            runner = float(scored[1]["score"]) if len(scored) > 1 else 0.0
            margin = winner - runner
            if winner >= args.score_min and margin >= args.winner_margin:
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
            "winner_margin": round(margin, 4) if margin is not None else None,
            "candidate_scores": scored,
        })

    result = {
        "meta": {
            "stage": "GLOBAL_PATH_CONTINUITY_OWNERSHIP_RESOLUTION",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "input_ambiguous_fragment_count": len(records),
            "resolved_fragment_count": resolved,
            "remaining_ambiguous_fragment_count": ambiguous,
            "completion_gate": "remaining_ambiguous_fragment_count == 0",
        },
        "ownership_decisions": records,
    }
    (args.out / "global_ownership_resolution.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
