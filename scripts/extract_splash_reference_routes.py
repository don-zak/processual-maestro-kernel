#!/usr/bin/env python3
"""Extract and audit PCB routing from the approved Splash reference image.

This is an extraction tool only. It must never invent route topology or render a
replacement Splash. The approved reference image remains the source of truth.

The extractor separates route color families, confines analysis to measured
corridors around the central core, inventories visible core-pin candidates,
reconciles those pins with graph origins, and traces each matched origin to
reachable terminals. Every result remains non-canonical until visual audit.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

REFERENCE_CORE = (608, 224, 1041, 632)
REFERENCE_SIZE = (1672, 941)
EXECUTION_CENTER = (821, 724)
EXECUTION_RADIUS = 58
PIN_MATCH_RADIUS = 24.0

HUE_RANGES = {
    "amber": (7, 30),
    "lime": (34, 58),
    "teal": (76, 91),
    "cyan": (92, 118),
    "violet": (126, 160),
}

NEIGHBOURS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),             (0, 1),
    (1, -1),  (1, 0),    (1, 1),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="Approved reference PNG")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--saturation-min", type=int, default=70)
    parser.add_argument("--value-min", type=int, default=65)
    return parser.parse_args()


def route_corridor_roi(shape: tuple[int, int]) -> np.ndarray:
    """Return only the four measured regions in which core routes can exist."""
    h, w = shape
    roi = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(roi, (390, 52), (612, 770), 255, -1)
    cv2.rectangle(roi, (1037, 52), (1270, 770), 255, -1)
    cv2.rectangle(roi, (580, 52), (1090, 228), 255, -1)
    cv2.rectangle(roi, (570, 628), (1100, 790), 255, -1)
    cv2.rectangle(roi, (608, 224), (1041, 632), 0, -1)
    cv2.circle(roi, EXECUTION_CENTER, EXECUTION_RADIUS, 0, -1)
    return roi


def origin_band(shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    x1, y1, x2, y2 = REFERENCE_CORE
    band = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(band, (596, y1), (610, y2), 255, -1)
    cv2.rectangle(band, (1039, y1), (1053, y2), 255, -1)
    cv2.rectangle(band, (x1, 212), (x2, 226), 255, -1)
    cv2.rectangle(band, (x1, 630), (x2, 644), 255, -1)
    return band


def color_masks(image: np.ndarray, saturation_min: int, value_min: int) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    roi = route_corridor_roi(image.shape[:2])
    masks: dict[str, np.ndarray] = {}
    for name, (lo, hi) in HUE_RANGES.items():
        selected = (
            (hue >= lo)
            & (hue <= hi)
            & (saturation >= saturation_min)
            & (value >= value_min)
        ).astype(np.uint8) * 255
        masks[name] = cv2.bitwise_and(selected, roi)
    return masks


def retain_core_connected(mask: np.ndarray, origin: np.ndarray) -> tuple[np.ndarray, int]:
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats((closed > 0).astype(np.uint8), 8)
    keep = np.zeros_like(closed)
    kept_components = 0
    for label_id in range(1, count):
        component = labels == label_id
        if stats[label_id, cv2.CC_STAT_AREA] < 5:
            continue
        if np.any(component & (origin > 0)):
            keep[component] = 255
            kept_components += 1
    return keep, kept_components


def neighbours(pixel: tuple[int, int], pixels: set[tuple[int, int]]) -> list[tuple[int, int]]:
    y, x = pixel
    return [(y + dy, x + dx) for dy, dx in NEIGHBOURS if (y + dy, x + dx) in pixels]


def edge_key(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def trace_graph_edges(skeleton: np.ndarray) -> tuple[list[list[tuple[int, int]]], set[tuple[int, int]], set[tuple[int, int]]]:
    pixels = set(map(tuple, np.argwhere(skeleton).tolist()))
    nodes = {pixel for pixel in pixels if len(neighbours(pixel, pixels)) != 2}
    visited: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    chains: list[list[tuple[int, int]]] = []
    for start in nodes:
        for candidate in neighbours(start, pixels):
            if edge_key(start, candidate) in visited:
                continue
            chain = [start]
            previous = start
            current = candidate
            visited.add(edge_key(start, candidate))
            while True:
                chain.append(current)
                if current in nodes and current != start:
                    break
                options = [
                    item for item in neighbours(current, pixels)
                    if item != previous and edge_key(current, item) not in visited
                ]
                if not options:
                    break
                vy, vx = current[0] - previous[0], current[1] - previous[1]
                options.sort(
                    key=lambda item: -(
                        vy * (item[0] - current[0]) + vx * (item[1] - current[1])
                    )
                )
                next_pixel = options[0]
                visited.add(edge_key(current, next_pixel))
                previous, current = current, next_pixel
            if len(chain) >= 3:
                chains.append(chain)
    return chains, pixels, nodes


def rdp(points: list[tuple[float, float]], epsilon: float = 1.0) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    a = np.array(points[0], dtype=float)
    b = np.array(points[-1], dtype=float)
    ab = b - a
    norm = np.linalg.norm(ab)
    distances = []
    for point in points:
        p = np.array(point, dtype=float)
        if norm < 1e-9:
            distances.append(float(np.linalg.norm(p - a)))
        else:
            distances.append(float(abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / norm))
    index = int(np.argmax(distances))
    if distances[index] > epsilon:
        left = rdp(points[: index + 1], epsilon)
        right = rdp(points[index:], epsilon)
        return left[:-1] + right
    return [points[0], points[-1]]


def core_distance(x: float, y: float) -> float:
    x1, y1, x2, y2 = REFERENCE_CORE
    if y1 - 18 <= y <= y2 + 18:
        return min(abs(x - x1), abs(x - x2))
    if x1 - 18 <= x <= x2 + 18:
        return min(abs(y - y1), abs(y - y2))
    dx = 0 if x1 <= x <= x2 else min(abs(x - x1), abs(x - x2))
    dy = 0 if y1 <= y <= y2 else min(abs(y - y1), abs(y - y2))
    return math.hypot(dx, dy)


def side_for(x: float, y: float) -> str:
    x1, y1, x2, y2 = REFERENCE_CORE
    return min(
        (("left", abs(x - x1)), ("right", abs(x - x2)), ("top", abs(y - y1)), ("bottom", abs(y - y2))),
        key=lambda item: item[1],
    )[0]


def simple_peaks(profile: np.ndarray, *, distance: int = 8, prominence: float = 12.0, height: float = 75.0) -> list[int]:
    """Small dependency-free 1D peak detector for the core tooth profiles."""
    candidates = [
        index for index in range(1, len(profile) - 1)
        if profile[index] >= height
        and profile[index] >= profile[index - 1]
        and profile[index] > profile[index + 1]
        and profile[index] - min(profile[index - 1], profile[index + 1]) >= prominence
    ]
    accepted: list[int] = []
    for index in sorted(candidates, key=lambda item: float(profile[item]), reverse=True):
        if all(abs(index - other) >= distance for other in accepted):
            accepted.append(index)
    return sorted(accepted)


def detect_pin_candidates(image: np.ndarray) -> list[dict[str, object]]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, saturation, value = cv2.split(hsv)
    score = value.astype(float) * (saturation.astype(float) / 255.0)
    x1, y1, x2, y2 = REFERENCE_CORE
    profiles = {
        "left": score[y1:y2, 596:606].max(axis=1),
        "right": score[y1:y2, 1043:1053].max(axis=1),
        "top": score[212:222, x1:x2].max(axis=0),
        "bottom": score[634:644, x1:x2].max(axis=0),
    }
    pins: list[dict[str, object]] = []
    for side, profile in profiles.items():
        peaks = simple_peaks(profile)
        peaks = [peak for peak in peaks if 5 < peak < len(profile) - 6]
        for peak in peaks:
            if side == "left":
                x, y = 601, y1 + int(peak)
            elif side == "right":
                x, y = 1048, y1 + int(peak)
            elif side == "top":
                x, y = x1 + int(peak), 217
            else:
                x, y = x1 + int(peak), 639
            pins.append({
                "id": f"pin-candidate-{len(pins) + 1:03d}",
                "side": side,
                "x": x,
                "y": y,
                "profile_score": round(float(profile[peak]), 2),
                "status": "AUDIT_REQUIRED",
            })
    return pins


def node_key(color: str, x: int, y: int) -> tuple[str, int, int]:
    return color, x, y


def reconcile_pins(
    pins: list[dict[str, object]],
    nodes: list[dict[str, object]],
    edges: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Attach measured pin candidates to nearby graph origins and trace terminals."""
    origins = [node for node in nodes if node["type"] == "origin-candidate"]
    node_by_key = {
        node_key(str(node["color"]), int(node["x"]), int(node["y"])): node
        for node in nodes
    }
    adjacency: dict[tuple[str, int, int], list[tuple[tuple[str, int, int], str]]] = defaultdict(list)
    for edge in edges:
        points = edge["points"]
        assert isinstance(points, list) and len(points) >= 2
        sx, sy = points[0]
        ex, ey = points[-1]
        a = node_key(str(edge["color"]), int(round(sx)), int(round(sy)))
        b = node_key(str(edge["color"]), int(round(ex)), int(round(ey)))
        adjacency[a].append((b, str(edge["id"])))
        adjacency[b].append((a, str(edge["id"])))

    reconciled: list[dict[str, object]] = []
    for pin in pins:
        px, py = int(pin["x"]), int(pin["y"])
        side = str(pin["side"])
        candidates = []
        for origin in origins:
            if origin.get("side") != side:
                continue
            distance = math.hypot(px - int(origin["x"]), py - int(origin["y"]))
            if distance <= PIN_MATCH_RADIUS:
                candidates.append((distance, origin))
        candidates.sort(key=lambda item: item[0])
        record = dict(pin)
        if not candidates:
            record.update({
                "matched": False,
                "origin_node_id": None,
                "origin_distance_px": None,
                "terminal_paths": [],
            })
            reconciled.append(record)
            continue

        distance, origin = candidates[0]
        origin_key = node_key(str(origin["color"]), int(origin["x"]), int(origin["y"]))
        terminal_paths: list[dict[str, object]] = []
        stack: list[tuple[tuple[str, int, int], list[str], set[tuple[str, int, int]]]] = [
            (origin_key, [], {origin_key})
        ]
        while stack:
            current, path_edges, visited_nodes = stack.pop()
            current_node = node_by_key.get(current)
            if current != origin_key and current_node and current_node["type"] == "terminal":
                terminal_paths.append({
                    "terminal_node_id": current_node["id"],
                    "edge_ids": path_edges,
                })
                continue
            for next_key, edge_id in adjacency.get(current, []):
                if next_key in visited_nodes:
                    continue
                stack.append((next_key, path_edges + [edge_id], visited_nodes | {next_key}))

        record.update({
            "matched": True,
            "origin_node_id": origin["id"],
            "origin_distance_px": round(distance, 2),
            "route_color": origin["color"],
            "terminal_paths": terminal_paths,
            "status": "AUDIT_REQUIRED",
        })
        reconciled.append(record)
    return reconciled


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Cannot read reference image: {args.image}")
    h, w = image.shape[:2]
    if (w, h) != REFERENCE_SIZE:
        raise SystemExit(f"Reference size changed: {(w, h)} != {REFERENCE_SIZE}")

    origin = origin_band((h, w))
    masks = color_masks(image, args.saturation_min, args.value_min)
    edges: list[dict[str, object]] = []
    nodes: list[dict[str, object]] = []
    selected_masks: dict[str, np.ndarray] = {}
    color_stats: dict[str, object] = {}

    for color, mask in masks.items():
        selected, component_count = retain_core_connected(mask, origin)
        selected_masks[color] = selected
        skeleton = skeletonize(selected > 0)
        chains, pixels, graph_nodes = trace_graph_edges(skeleton)
        degree = {pixel: len(neighbours(pixel, pixels)) for pixel in graph_nodes}
        node_ids: dict[tuple[int, int], str] = {}

        for y, x in sorted(graph_nodes):
            distance = core_distance(x, y)
            node_type = "junction" if degree[(y, x)] >= 3 else "terminal"
            if distance <= 17:
                node_type = "origin-candidate"
            node_id = f"node-{len(nodes) + 1:04d}"
            node_ids[(y, x)] = node_id
            nodes.append({
                "id": node_id,
                "x": int(x),
                "y": int(y),
                "color": color,
                "degree": int(degree[(y, x)]),
                "type": node_type,
                "side": side_for(x, y) if node_type == "origin-candidate" else None,
            })

        color_edge_start = len(edges)
        for chain in chains:
            raw_start = chain[0]
            raw_end = chain[-1]
            points = rdp([(float(x), float(y)) for y, x in chain])
            length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
            if length < 6:
                continue
            start_node_id = node_ids.get(raw_start)
            end_node_id = node_ids.get(raw_end)
            if core_distance(*points[-1]) < core_distance(*points[0]):
                points.reverse()
                start_node_id, end_node_id = end_node_id, start_node_id
            edges.append({
                "id": f"edge-{len(edges) + 1:04d}",
                "color": color,
                "length_px": round(length, 2),
                "origin_edge": core_distance(*points[0]) <= 17,
                "start_node_id": start_node_id,
                "end_node_id": end_node_id,
                "points": [[round(x, 1), round(y, 1)] for x, y in points],
            })

        color_stats[color] = {
            "kept_components": component_count,
            "selected_pixels": int((selected > 0).sum()),
            "skeleton_pixels": int(skeleton.sum()),
            "graph_edges": len(edges) - color_edge_start,
        }

    pins = detect_pin_candidates(image)
    reconciled_pins = reconcile_pins(pins, nodes, edges)
    pin_counts = {
        side: sum(pin["side"] == side for pin in reconciled_pins)
        for side in ("left", "right", "top", "bottom")
    }
    matched_count = sum(bool(pin["matched"]) for pin in reconciled_pins)
    path_count = sum(len(pin["terminal_paths"]) for pin in reconciled_pins)
    manifest = {
        "meta": {
            "source": args.image.name,
            "width": w,
            "height": h,
            "core_bounds": list(REFERENCE_CORE),
            "method": "exclusive-HSV + measured corridors + per-color graph + pin-origin reconciliation",
            "edge_count": len(edges),
            "node_count": len(nodes),
            "pin_candidate_count": len(reconciled_pins),
            "matched_pin_count": matched_count,
            "unmatched_pin_count": len(reconciled_pins) - matched_count,
            "terminal_path_count": path_count,
            "pin_candidates_by_side": pin_counts,
            "color_stats": color_stats,
            "status": "AUDIT_REQUIRED",
            "canonical": False,
            "splash_reconstruction_allowed": False,
        },
        "pin_candidates": reconciled_pins,
        "nodes": nodes,
        "edges": edges,
    }
    (args.out / "reference_route_graph_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    combined = np.zeros((h, w), dtype=np.uint8)
    overlay = image.copy()
    for selected in selected_masks.values():
        combined |= selected
        overlay[skeletonize(selected > 0)] = (245, 245, 245)
    for pin in reconciled_pins:
        center = (int(pin["x"]), int(pin["y"]))
        cv2.circle(overlay, center, 4, (0, 255, 0) if pin["matched"] else (0, 0, 255), 1)
    for node in nodes:
        center = (int(node["x"]), int(node["y"]))
        if node["type"] == "terminal":
            cv2.circle(overlay, center, 2, (0, 0, 255), -1)
        elif node["type"] == "junction":
            cv2.circle(overlay, center, 2, (0, 255, 255), -1)

    cv2.imwrite(str(args.out / "reference_route_graph_mask.png"), combined)
    cv2.imwrite(str(args.out / "reference_route_graph_overlay.png"), overlay)
    print(json.dumps(manifest["meta"], indent=2))


if __name__ == "__main__":
    main()
