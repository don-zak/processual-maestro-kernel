#!/usr/bin/env python3
"""Extract and audit PCB routing from the approved Splash reference image.

This is an extraction tool only. It must never invent route topology or render a
replacement Splash. The approved reference image remains the source of truth.

The extractor now separates the five route color families, confines analysis to
measured route corridors around the central core, inventories visible core-pin
candidates, and emits a non-canonical graph for tile-by-tile audit.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.signal import find_peaks
from skimage.morphology import skeletonize

REFERENCE_CORE = (608, 224, 1041, 632)
REFERENCE_SIZE = (1672, 941)
EXECUTION_CENTER = (821, 724)
EXECUTION_RADIUS = 58

# Deliberately non-overlapping hue bands. The previous cyan/teal overlap made
# color classification ambiguous and inflated cyan route counts.
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
    # Closing only two pixels repairs antialias gaps without intentionally
    # bridging adjacent PCB lanes.
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


def detect_pin_candidates(image: np.ndarray) -> list[dict[str, object]]:
    """Inventory bright teeth from measured strips immediately outside the core.

    These are audit candidates, not yet canonical pin identities. The output is
    intentionally kept separate from the route graph until every peak has been
    reconciled against the reference overlay.
    """
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
        peaks, _ = find_peaks(profile, distance=8, prominence=12, height=75)
        peaks = peaks[(peaks > 5) & (peaks < len(profile) - 6)]
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

        for y, x in graph_nodes:
            distance = core_distance(x, y)
            node_type = "junction" if degree[(y, x)] >= 3 else "terminal"
            if distance <= 17:
                node_type = "origin-candidate"
            nodes.append({
                "x": int(x),
                "y": int(y),
                "color": color,
                "degree": int(degree[(y, x)]),
                "type": node_type,
                "side": side_for(x, y) if node_type == "origin-candidate" else None,
            })

        color_edge_start = len(edges)
        for chain in chains:
            points = rdp([(float(x), float(y)) for y, x in chain])
            length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
            if length < 6:
                continue
            if core_distance(*points[-1]) < core_distance(*points[0]):
                points.reverse()
            edges.append({
                "id": f"edge-{len(edges) + 1:04d}",
                "color": color,
                "length_px": round(length, 2),
                "origin_edge": core_distance(*points[0]) <= 17,
                "points": [[round(x, 1), round(y, 1)] for x, y in points],
            })

        color_stats[color] = {
            "kept_components": component_count,
            "selected_pixels": int((selected > 0).sum()),
            "skeleton_pixels": int(skeleton.sum()),
            "graph_edges": len(edges) - color_edge_start,
        }

    pins = detect_pin_candidates(image)
    pin_counts = {side: sum(pin["side"] == side for pin in pins) for side in ("left", "right", "top", "bottom")}
    manifest = {
        "meta": {
            "source": args.image.name,
            "width": w,
            "height": h,
            "core_bounds": list(REFERENCE_CORE),
            "method": "exclusive-HSV + measured route corridors + per-color core-connected skeleton graph",
            "edge_count": len(edges),
            "node_count": len(nodes),
            "pin_candidate_count": len(pins),
            "pin_candidates_by_side": pin_counts,
            "color_stats": color_stats,
            "status": "AUDIT_REQUIRED",
            "canonical": False,
            "splash_reconstruction_allowed": False,
        },
        "pin_candidates": pins,
        "nodes": nodes,
        "edges": edges,
    }
    (args.out / "reference_route_graph_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    combined = np.zeros((h, w), dtype=np.uint8)
    overlay = image.copy()
    for selected in selected_masks.values():
        combined |= selected
        overlay[skeletonize(selected > 0)] = (245, 245, 245)
    for pin in pins:
        cv2.circle(overlay, (int(pin["x"]), int(pin["y"])), 4, (0, 255, 0), 1)
    for node in nodes:
        if node["type"] == "terminal":
            cv2.circle(overlay, (int(node["x"]), int(node["y"])), 2, (0, 0, 255), -1)
        elif node["type"] == "junction":
            cv2.circle(overlay, (int(node["x"]), int(node["y"])), 2, (0, 255, 255), -1)

    cv2.imwrite(str(args.out / "reference_route_graph_mask.png"), combined)
    cv2.imwrite(str(args.out / "reference_route_graph_overlay.png"), overlay)
    print(json.dumps(manifest["meta"], indent=2))


if __name__ == "__main__":
    main()
