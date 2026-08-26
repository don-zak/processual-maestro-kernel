#!/usr/bin/env python3
"""Resolve remaining ambiguous Splash fragments by Manhattan-sequence continuity.

This third-pass resolver compares the ordered bend/direction sequence of each
preserved fragment with wider neighborhoods of candidate pin trees. It does not
add, delete, or move pixels. A candidate may win only when its directional run
sequence, bend order, endpoint approach, and radial progression agree with the
fragment by a strict margin. Otherwise the fragment remains SHARED_GEOMETRY or
AMBIGUOUS and canonical promotion stays blocked.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

import numpy as np

CORE = (608, 224, 1041, 632)
NEIGHBOURS = ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("reconciliation_audit", type=Path)
    p.add_argument("partition_audit", type=Path)
    p.add_argument("global_ownership", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tree-radius", type=float, default=64.0)
    p.add_argument("--gap-max", type=float, default=14.0)
    p.add_argument("--score-min", type=float, default=7.0)
    p.add_argument("--winner-margin", type=float, default=1.5)
    return p.parse_args()


def core_distance(x: int, y: int) -> float:
    x1,y1,x2,y2 = CORE
    dx = 0 if x1 <= x <= x2 else min(abs(x-x1), abs(x-x2))
    dy = 0 if y1 <= y <= y2 else min(abs(y-y1), abs(y-y2))
    return math.hypot(dx, dy)


def degree_map(points: set[tuple[int,int]]) -> dict[tuple[int,int], int]:
    return {
        p: sum((p[0]+dx, p[1]+dy) in points for dy,dx in NEIGHBOURS)
        for p in points
    }


def endpoints(points: set[tuple[int,int]]) -> list[tuple[int,int]]:
    d = degree_map(points)
    result = [p for p,v in d.items() if v <= 1]
    return result or list(points)


def ordered_path(points: set[tuple[int,int]], start: tuple[int,int] | None = None, limit: int = 256) -> list[tuple[int,int]]:
    if not points:
        return []
    if start is None:
        start = min(endpoints(points), key=lambda p: core_distance(*p))
    path = [start]
    prev = None
    cur = start
    seen = {start}
    while len(path) < limit:
        options = [
            (cur[0]+dx, cur[1]+dy)
            for dy,dx in NEIGHBOURS
            if (cur[0]+dx, cur[1]+dy) in points and (cur[0]+dx, cur[1]+dy) != prev
        ]
        options = [p for p in options if p not in seen]
        if not options:
            break
        options.sort(key=lambda p: core_distance(*p), reverse=True)
        nxt = options[0]
        prev, cur = cur, nxt
        seen.add(cur)
        path.append(cur)
    return path


def direction(a: tuple[int,int], b: tuple[int,int]) -> str:
    dx, dy = b[0]-a[0], b[1]-a[1]
    if abs(dx) >= abs(dy):
        return "E" if dx >= 0 else "W"
    return "S" if dy >= 0 else "N"


def run_sequence(path: list[tuple[int,int]]) -> list[tuple[str,int]]:
    if len(path) < 2:
        return []
    dirs = [direction(a,b) for a,b in zip(path, path[1:])]
    runs: list[tuple[str,int]] = []
    for d in dirs:
        if runs and runs[-1][0] == d:
            runs[-1] = (d, runs[-1][1] + 1)
        else:
            runs.append((d,1))
    return runs


def sequence_similarity(a: list[tuple[str,int]], b: list[tuple[str,int]]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b), 8)
    if n == 0:
        return 0.0
    score = 0.0
    for i in range(1, n+1):
        da, la = a[-i]
        db, lb = b[-i]
        if da == db:
            length_ratio = min(la, lb) / max(la, lb)
            score += 0.65 + 0.35 * length_ratio
    return score / n


def nearest_pair(region: set[tuple[int,int]], tree: set[tuple[int,int]]) -> tuple[float, tuple[int,int] | None, tuple[int,int] | None]:
    best = (math.inf, None, None)
    for rp in endpoints(region):
        for tp in tree:
            gap = math.hypot(rp[0]-tp[0], rp[1]-tp[1])
            if gap < best[0]:
                best = (gap, rp, tp)
    return best


def crop_tree(tree: set[tuple[int,int]], contact: tuple[int,int], radius: float) -> set[tuple[int,int]]:
    cx,cy = contact
    return {p for p in tree if math.hypot(p[0]-cx, p[1]-cy) <= radius}


def score(region: set[tuple[int,int]], tree: set[tuple[int,int]], base: float, radius: float, gap_max: float) -> dict[str, object]:
    gap, rp, tp = nearest_pair(region, tree)
    if rp is None or tp is None or gap > gap_max:
        return {"score": round(base,4), "gap_px": None, "sequence_similarity": 0.0, "bend_order_match": False, "outward_progression": False}

    region_path = ordered_path(region)
    local_tree = crop_tree(tree, tp, radius)
    tree_path = ordered_path(local_tree, start=tp)
    region_seq = run_sequence(region_path)
    tree_seq = run_sequence(tree_path)
    sim = sequence_similarity(region_seq, tree_seq)

    bend_match = False
    if len(region_seq) >= 2 and len(tree_seq) >= 2:
        bend_match = region_seq[-1][0] == tree_seq[-1][0] and region_seq[-2][0] == tree_seq[-2][0]

    outward = core_distance(*rp) >= core_distance(*tp)
    gap_score = max(0.0, 1.0 - gap / gap_max)
    total = base + sim*4.0 + (1.5 if bend_match else 0.0) + (1.0 if outward else 0.0) + gap_score*1.5
    return {
        "score": round(total,4),
        "gap_px": round(gap,3),
        "sequence_similarity": round(sim,4),
        "bend_order_match": bend_match,
        "outward_progression": outward,
        "region_sequence": region_seq[-8:],
        "tree_sequence": tree_seq[-8:],
    }


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    audit = json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    partition = json.loads(args.partition_audit.read_text(encoding="utf-8"))
    global_result = json.loads(args.global_ownership.read_text(encoding="utf-8"))

    regions = {str(r["id"]): r for r in audit.get("regions", [])}
    tree_pixels = partition.get("route_tree_pixels")
    if not isinstance(tree_pixels, dict):
        raise SystemExit("partition audit lacks route_tree_pixels")

    records = []
    resolved = 0
    shared = 0
    ambiguous = 0
    for item in global_result.get("ownership_decisions", []):
        if item.get("decision") != "AMBIGUOUS":
            continue
        region_id = str(item["region"])
        region = {(int(x),int(y)) for x,y in regions[region_id].get("pixels", [])}
        candidates = []
        for candidate in item.get("candidate_scores", []):
            tree_id = int(candidate["tree_id"])
            tree = {(int(x),int(y)) for x,y in tree_pixels.get(str(tree_id), [])}
            evidence = score(region, tree, float(candidate["score"]), args.tree_radius, args.gap_max)
            evidence["tree_id"] = tree_id
            candidates.append(evidence)
        candidates.sort(key=lambda r: float(r["score"]), reverse=True)

        decision = "AMBIGUOUS"
        target_tree = None
        margin = None
        if candidates:
            winner = float(candidates[0]["score"])
            runner = float(candidates[1]["score"]) if len(candidates) > 1 else 0.0
            margin = winner - runner
            if winner >= args.score_min and margin >= args.winner_margin:
                decision = "ATTACH_CONTINUATION"
                target_tree = int(candidates[0]["tree_id"])
                resolved += 1
            elif len(candidates) >= 2 and abs(margin) < 0.35 and all(float(c["sequence_similarity"]) >= 0.7 for c in candidates[:2]):
                decision = "SHARED_GEOMETRY"
                shared += 1
            else:
                ambiguous += 1
        else:
            ambiguous += 1

        records.append({
            "region": region_id,
            "decision": decision,
            "target_tree": target_tree,
            "winner_margin": round(margin,4) if margin is not None else None,
            "candidate_scores": candidates,
        })

    result = {
        "meta": {
            "stage": "MANHATTAN_SEQUENCE_OWNERSHIP_RESOLUTION",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "input_ambiguous_fragment_count": len(records),
            "resolved_fragment_count": resolved,
            "shared_geometry_count": shared,
            "remaining_ambiguous_fragment_count": ambiguous,
            "completion_gate": "remaining_ambiguous_fragment_count == 0",
        },
        "ownership_decisions": records,
    }
    (args.out / "manhattan_ownership_resolution.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
