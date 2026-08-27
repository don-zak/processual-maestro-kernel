#!/usr/bin/env python3
"""Audit canonical Splash route terminals near the eight side cards.

This stage is deliberately audit-only. It identifies short/near-card terminal
candidates that require visual comparison with the approved pivot reference.
It NEVER extends a route, changes a path, or assigns a card connection merely
because a terminal is geometrically close to a card.

Inputs:
- runtime_manifest: output of build_splash_runtime_manifest.py
- layout_contract: JSON containing eight side-card rectangles in reference-space
  coordinates. Rectangles are review geometry only, not route geometry.

Output classifications are intentionally conservative:
- intentional-board-terminal: only when explicitly pre-reviewed in layout input
- reference-backed-card-connection: only when explicitly pre-reviewed
- renderer-or-transform-fragment: only when explicitly pre-reviewed
- review-required: every unreviewed candidate
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

REFERENCE_SIZE = [1672, 941]
ALLOWED_REVIEW_DECISIONS = {
    "intentional-board-terminal",
    "reference-backed-card-connection",
    "renderer-or-transform-fragment",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime_manifest", type=Path)
    parser.add_argument("layout_contract", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--halo", type=float, default=42.0)
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def point_rect_distance(x: float, y: float, rect: list[int]) -> float:
    left, top, right, bottom = rect
    dx = max(left - x, 0.0, x - right)
    dy = max(top - y, 0.0, y - bottom)
    return math.hypot(dx, dy)


def card_side_distance(x: float, y: float, rect: list[int], side: str) -> float:
    left, top, right, bottom = rect
    if side == "left":
        edge_x = right
    elif side == "right":
        edge_x = left
    else:
        raise SystemExit(f"Unsupported side-card side: {side}")
    vertical = max(top - y, 0.0, y - bottom)
    return math.hypot(x - edge_x, vertical)


def terminal_key(tree_id: int, x: int, y: int) -> str:
    return f"tree-{tree_id:03d}@{x},{y}"


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.runtime_manifest.read_text(encoding="utf-8"))
    layout = json.loads(args.layout_contract.read_text(encoding="utf-8"))

    meta = manifest.get("meta", {})
    require(meta.get("reference_size") == REFERENCE_SIZE, "Runtime manifest reference size mismatch")
    require(int(meta.get("route_tree_count", 0)) == 125, "Runtime manifest must contain 125 route trees")
    require(not bool(meta.get("procedural_generation_allowed", True)), "Procedural route generation must remain disabled")
    require(not bool(meta.get("hand_authored_route_extension_allowed", True)), "Hand-authored route extension must remain disabled")

    cards = layout.get("side_cards", [])
    require(isinstance(cards, list) and len(cards) == 8, "Layout contract must define exactly eight side cards")
    normalized_cards: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for card in cards:
        require(isinstance(card, dict), "Invalid side-card layout record")
        name = str(card.get("name", ""))
        side = str(card.get("side", ""))
        bounds = card.get("bounds")
        require(name and name not in seen_names, f"Invalid or duplicate side-card name: {name}")
        require(side in {"left", "right"}, f"Invalid side for card {name}")
        require(isinstance(bounds, list) and len(bounds) == 4, f"Invalid bounds for card {name}")
        rect = [int(value) for value in bounds]
        require(0 <= rect[0] < rect[2] < REFERENCE_SIZE[0], f"Invalid horizontal bounds for {name}")
        require(0 <= rect[1] < rect[3] < REFERENCE_SIZE[1], f"Invalid vertical bounds for {name}")
        seen_names.add(name)
        normalized_cards.append({"name": name, "side": side, "bounds": rect})

    reviewed = layout.get("reviewed_terminal_decisions", {})
    require(isinstance(reviewed, dict), "reviewed_terminal_decisions must be an object")
    for key, decision in reviewed.items():
        require(str(decision) in ALLOWED_REVIEW_DECISIONS, f"Invalid reviewed decision for {key}: {decision}")

    candidates: list[dict[str, object]] = []
    decisions = defaultdict(int)
    candidate_keys: set[str] = set()

    for tree in manifest.get("route_trees", []):
        require(isinstance(tree, dict), "Invalid route tree record")
        tree_id = int(tree["tree_id"])
        tree_side = str(tree.get("side", ""))
        if tree_side not in {"left", "right"}:
            continue
        terminals = tree.get("terminals", [])
        require(isinstance(terminals, list), f"Invalid terminals for tree {tree_id}")
        relevant_cards = [card for card in normalized_cards if card["side"] == tree_side]
        for point in terminals:
            require(isinstance(point, list) and len(point) == 2, f"Invalid terminal in tree {tree_id}")
            x, y = int(point[0]), int(point[1])
            ranked = sorted(
                (
                    (
                        card_side_distance(x, y, card["bounds"], tree_side),
                        point_rect_distance(x, y, card["bounds"]),
                        card,
                    )
                    for card in relevant_cards
                ),
                key=lambda item: (item[0], item[1], str(item[2]["name"])),
            )
            edge_distance, rect_distance, nearest = ranked[0]
            if edge_distance > args.halo:
                continue
            key = terminal_key(tree_id, x, y)
            require(key not in candidate_keys, f"Duplicate terminal candidate: {key}")
            candidate_keys.add(key)
            decision = str(reviewed.get(key, "review-required"))
            decisions[decision] += 1
            candidates.append(
                {
                    "terminal_key": key,
                    "tree_id": tree_id,
                    "tree_side": tree_side,
                    "terminal": [x, y],
                    "nearest_card": nearest["name"],
                    "nearest_card_bounds": nearest["bounds"],
                    "distance_to_inward_card_edge_px": round(edge_distance, 3),
                    "distance_to_card_rect_px": round(rect_distance, 3),
                    "classification": decision,
                    "geometry_modified": False,
                }
            )

    candidates.sort(key=lambda item: (float(item["distance_to_inward_card_edge_px"]), int(item["tree_id"])))
    result = {
        "meta": {
            "stage": "SHORT_ROUTE_REACH_AUDIT",
            "source_of_truth": "canonical runtime manifest + approved-reference card layout review contract",
            "halo_px": float(args.halo),
            "candidate_count": len(candidates),
            "classification_counts": dict(decisions),
            "geometry_modified": False,
            "automatic_route_extension_performed": False,
            "visual_review_required": decisions.get("review-required", 0) > 0,
            "acceptance_ready": decisions.get("review-required", 0) == 0,
        },
        "candidates": candidates,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
