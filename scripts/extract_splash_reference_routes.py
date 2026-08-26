#!/usr/bin/env python3
"""Extract the PCB routing graph from the approved Splash reference image.

This script is intentionally an extraction/audit tool, not a Splash renderer.
It preserves the reference image as the source of truth and emits:
  * a pixel-derived route mask;
  * a skeleton graph;
  * vector edge geometry between graph nodes;
  * a visual audit overlay.

The generated data MUST be visually audited before it can be promoted to the
canonical Splash routing manifest. No procedural route generation is allowed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

REFERENCE_CORE = (608, 224, 1041, 632)  # x1, y1, x2, y2 on 1672x941 reference
REFERENCE_SIZE = (1672, 941)

# OpenCV HSV hue bands for the five reference route families.
HUE_RANGES = {
    "cyan": ((88, 118),),
    "teal": ((76, 93),),
    "lime": ((34, 58),),
    "amber": ((7, 30),),
    "violet": ((126, 160),),
}

# UI card interiors are excluded so their outlines/icons/text cannot be
# mistaken for PCB routing. Their connector-facing edges remain auditable from
# the original image and can later be reconciled explicitly.
MODULE_BOXES = (
    (65, 80, 410, 237),
    (65, 247, 410, 407),
    (65, 417, 410, 579),
    (65, 588, 410, 754),
    (1255, 80, 1590, 237),
    (1255, 247, 1590, 407),
    (1255, 417, 1590, 579),
    (1255, 588, 1590, 754),
)

NEIGHBOURS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),             (0, 1),
    (1, -1),  (1, 0),    (1, 1),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="Approved reference PNG")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("core-connected", "full-field"),
        default="core-connected",
        help="core-connected is the canonical tracing candidate; full-field is an audit surface",
    )
    parser.add_argument("--connectivity", type=int, choices=(3, 5, 7, 9), default=7)
    return parser.parse_args()


def color_masks(image: np.ndarray) -> dict[str, np.ndarray]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    result: dict[str, np.ndarray] = {}
    for name, ranges in HUE_RANGES.items():
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        for lo, hi in ranges:
            mask |= cv2.inRange(
                hsv,
                np.array([lo, 60, 48]),
                np.array([hi, 255, 255]),
            )
        result[name] = mask
    return result


def field_roi(shape: tuple[int, int], core: tuple[int, int, int, int]) -> np.ndarray:
    h, w = shape
    roi = np.full((h, w), 255, dtype=np.uint8)
    roi[:52, :] = 0
    roi[883:, :] = 0
    x1, y1, x2, y2 = core
    roi[y1 + 5 : y2 - 5, x1 + 5 : x2 - 5] = 0
    for left, top, right, bottom in MODULE_BOXES:
        roi[top:bottom, left:right] = 0
    return roi


def origin_band(shape: tuple[int, int], core: tuple[int, int, int, int]) -> np.ndarray:
    h, w = shape
    x1, y1, x2, y2 = core
    band = np.zeros((h, w), dtype=np.uint8)
    band[max(0, y1 - 12) : min(h, y2 + 12), max(0, x1 - 14) : min(w, x1 + 14)] = 1
    band[max(0, y1 - 12) : min(h, y2 + 12), max(0, x2 - 14) : min(w, x2 + 14)] = 1
    band[max(0, y1 - 14) : min(h, y1 + 14), max(0, x1 - 12) : min(w, x2 + 12)] = 1
    band[max(0, y2 - 14) : min(h, y2 + 14), max(0, x1 - 12) : min(w, x2 + 12)] = 1
    return band


def retain_route_surface(
    field: np.ndarray,
    origin: np.ndarray,
    mode: str,
    connectivity: int,
) -> np.ndarray:
    if mode == "full-field":
        return field

    connected = cv2.dilate(field, np.ones((connectivity, connectivity), np.uint8), iterations=1)
    count, labels, stats, _ = cv2.connectedComponentsWithStats((connected > 0).astype(np.uint8), 8)
    keep = np.zeros_like(field)
    for label in range(1, count):
        component = labels == label
        if stats[label, cv2.CC_STAT_AREA] < 6:
            continue
        if np.any(component & (origin > 0)):
            keep[component] = 255
    return cv2.bitwise_and(field, keep)


def neighbours(pixel: tuple[int, int], pixels: set[tuple[int, int]]) -> list[tuple[int, int]]:
    y, x = pixel
    return [(y + dy, x + dx) for dy, dx in NEIGHBOURS if (y + dy, x + dx) in pixels]


def edge_key(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def trace_graph_edges(skeleton: np.ndarray) -> list[list[tuple[int, int]]]:
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
                    item
                    for item in neighbours(current, pixels)
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
            if len(chain) >= 4:
                chains.append(chain)
    return chains


def rdp(points: list[tuple[float, float]], epsilon: float = 1.2) -> list[tuple[float, float]]:
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


def core_distance(point: tuple[float, float], core: tuple[int, int, int, int]) -> float:
    x, y = point
    x1, y1, x2, y2 = core
    candidates = []
    if y1 - 15 <= y <= y2 + 15:
        candidates.extend((abs(x - x1), abs(x - x2)))
    if x1 - 15 <= x <= x2 + 15:
        candidates.extend((abs(y - y1), abs(y - y2)))
    return min(candidates, default=99999.0)


def side_for(point: tuple[float, float], core: tuple[int, int, int, int]) -> str:
    x, y = point
    x1, y1, x2, y2 = core
    return min(
        (("left", abs(x - x1)), ("right", abs(x - x2)), ("top", abs(y - y1)), ("bottom", abs(y - y2))),
        key=lambda item: item[1],
    )[0]


def classify_color(chain: list[tuple[int, int]], masks: dict[str, np.ndarray]) -> str:
    counts = {name: 0 for name in masks}
    for y, x in chain:
        for name, mask in masks.items():
            counts[name] += int(mask[y, x] > 0)
    return max(counts, key=counts.get)


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.image))
    if image is None:
        raise SystemExit(f"Cannot read reference image: {args.image}")
    h, w = image.shape[:2]
    if (w, h) != REFERENCE_SIZE:
        raise SystemExit(f"Reference size changed: {(w, h)} != {REFERENCE_SIZE}")

    masks = color_masks(image)
    combined = np.zeros((h, w), dtype=np.uint8)
    for mask in masks.values():
        combined |= mask

    roi = field_roi((h, w), REFERENCE_CORE)
    field = cv2.bitwise_and(combined, roi)
    origin = origin_band((h, w), REFERENCE_CORE)
    selected = retain_route_surface(field, origin, args.mode, args.connectivity)
    selected = cv2.morphologyEx(selected, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    skeleton = skeletonize(selected > 0)

    chains = trace_graph_edges(skeleton)
    routes = []
    for chain in chains:
        points = rdp([(float(x), float(y)) for y, x in chain])
        length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
        if length < 7:
            continue
        if core_distance(points[-1], REFERENCE_CORE) < core_distance(points[0], REFERENCE_CORE):
            points.reverse()
        routes.append(
            {
                "id": f"route-edge-{len(routes) + 1:04d}",
                "origin": "core" if core_distance(points[0], REFERENCE_CORE) <= 15 else "field",
                "side": side_for(points[0], REFERENCE_CORE),
                "color": classify_color(chain, masks),
                "length_px": round(length, 2),
                "points": [[round(x, 1), round(y, 1)] for x, y in points],
            }
        )

    manifest = {
        "meta": {
            "source": args.image.name,
            "width": w,
            "height": h,
            "core_bounds": list(REFERENCE_CORE),
            "mode": args.mode,
            "connectivity": args.connectivity,
            "selected_pixel_count": int((selected > 0).sum()),
            "skeleton_pixel_count": int(skeleton.sum()),
            "edge_count": len(routes),
            "status": "AUDIT_REQUIRED",
            "canonical": False,
        },
        "routes": routes,
    }
    (args.out / "reference_route_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    cv2.imwrite(str(args.out / "reference_route_mask.png"), selected)

    overlay = image.copy()
    for route in routes:
        points = np.array(route["points"], np.int32).reshape((-1, 1, 2))
        cv2.polylines(overlay, [points], False, (255, 255, 255), 1, cv2.LINE_AA)
        sx, sy = map(int, route["points"][0])
        ex, ey = map(int, route["points"][-1])
        cv2.circle(overlay, (sx, sy), 2, (0, 255, 0), -1)
        cv2.circle(overlay, (ex, ey), 2, (0, 0, 255), -1)
    cv2.imwrite(str(args.out / "reference_route_overlay.png"), overlay)

    print(json.dumps(manifest["meta"], indent=2))


if __name__ == "__main__":
    main()
