#!/usr/bin/env python3
"""Partition the recovered Splash routing skeleton into one tree per core pin.

This stage resolves glow-induced merges without inventing geometry. It performs a
multi-source geodesic partition over the recovered skeleton, using the measured
core-pin attachment points as seeds. Pixels equidistant between competing pins
are marked as conflict boundaries instead of merging the two route trees.

The output remains audit-only and cannot promote the reference manifest to
canonical or enable Splash reconstruction. The audit now exports exact pixel
ownership for every pin-seeded route tree so later continuity analysis can resolve
visually verified KEEP fragments without falling back to proximity-only guesses.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

REFERENCE_SIZE = (1672, 941)
CORE = (608, 224, 1041, 632)
NEIGHBOURS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),             (0, 1),
    (1, -1),  (1, 0),    (1, 1),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("recovered_mask", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def peak_positions(profile: np.ndarray, min_height: float = 75.0, min_distance: int = 8) -> list[int]:
    candidates = [
        index
        for index in range(1, len(profile) - 1)
        if profile[index] >= min_height
        and profile[index] >= profile[index - 1]
        and profile[index] > profile[index + 1]
    ]
    accepted: list[int] = []
    for index in sorted(candidates, key=lambda item: float(profile[item]), reverse=True):
        if all(abs(index - other) >= min_distance for other in accepted):
            accepted.append(index)
    return sorted(accepted)


def detect_pins(image: np.ndarray) -> list[dict[str, int | str | float]]:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, saturation, value = cv2.split(hsv)
    score = value.astype(float) * saturation.astype(float) / 255.0
    x1, y1, x2, y2 = CORE
    profiles = {
        "left": score[y1:y2, 596:606].max(axis=1),
        "right": score[y1:y2, 1043:1053].max(axis=1),
        "top": score[212:222, x1:x2].max(axis=0),
        "bottom": score[634:644, x1:x2].max(axis=0),
    }
    pins: list[dict[str, int | str | float]] = []
    for side, profile in profiles.items():
        for peak in peak_positions(profile):
            if peak <= 5 or peak >= len(profile) - 6:
                continue
            if side == "left":
                x, y = 601, y1 + peak
            elif side == "right":
                x, y = 1048, y1 + peak
            elif side == "top":
                x, y = x1 + peak, 217
            else:
                x, y = x1 + peak, 639
            pins.append(
                {
                    "id": f"pin-{len(pins) + 1:03d}",
                    "side": side,
                    "x": x,
                    "y": y,
                    "score": round(float(profile[peak]), 2),
                }
            )
    return pins


def outward_window(pin: dict[str, int | str | float], shape: tuple[int, int]) -> tuple[slice, slice]:
    h, w = shape
    x, y = int(pin["x"]), int(pin["y"])
    side = str(pin["side"])
    if side == "left":
        return slice(max(0, y - 6), min(h, y + 7)), slice(max(0, x - 30), min(w, x + 10))
    if side == "right":
        return slice(max(0, y - 6), min(h, y + 7)), slice(max(0, x - 10), min(w, x + 31))
    if side == "top":
        return slice(max(0, y - 30), min(h, y + 10)), slice(max(0, x - 6), min(w, x + 7))
    return slice(max(0, y - 10), min(h, y + 31)), slice(max(0, x - 6), min(w, x + 7))


def attach_pin(pin: dict[str, int | str | float], skeleton: np.ndarray) -> tuple[int, int] | None:
    y_slice, x_slice = outward_window(pin, skeleton.shape)
    ys, xs = np.where(skeleton[y_slice, x_slice])
    if len(xs) == 0:
        return None
    origin_x, origin_y = int(pin["x"]), int(pin["y"])
    candidates = [
        (x_slice.start + int(x), y_slice.start + int(y))
        for y, x in zip(ys, xs)
    ]
    return min(
        candidates,
        key=lambda point: (point[0] - origin_x) ** 2 + (point[1] - origin_y) ** 2,
    )


def geodesic_partition(skeleton: np.ndarray, seeds: list[tuple[int, int, int]]) -> tuple[np.ndarray, np.ndarray]:
    h, w = skeleton.shape
    infinity = np.iinfo(np.int32).max
    distance = np.full((h, w), infinity, np.int32)
    labels = np.zeros((h, w), np.int32)
    queue: deque[tuple[int, int, int]] = deque()

    for y, x, pin_label in seeds:
        if distance[y, x] == 0 and labels[y, x] != pin_label:
            labels[y, x] = -1
            continue
        distance[y, x] = 0
        labels[y, x] = pin_label
        queue.append((y, x, pin_label))

    while queue:
        y, x, pin_label = queue.popleft()
        if labels[y, x] != pin_label:
            continue
        next_distance = distance[y, x] + 1
        for dy, dx in NEIGHBOURS:
            ny, nx = y + dy, x + dx
            if not (0 <= ny < h and 0 <= nx < w and skeleton[ny, nx]):
                continue
            if next_distance < distance[ny, nx]:
                distance[ny, nx] = next_distance
                labels[ny, nx] = pin_label
                queue.append((ny, nx, pin_label))
            elif next_distance == distance[ny, nx] and labels[ny, nx] not in (pin_label, -1):
                labels[ny, nx] = -1

    return labels, distance


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.reference))
    mask = cv2.imread(str(args.recovered_mask), cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None:
        raise SystemExit("Reference image or recovered route mask could not be read")
    h, w = image.shape[:2]
    if (w, h) != REFERENCE_SIZE or mask.shape != (h, w):
        raise SystemExit("Reference/mask geometry does not match the approved 1672x941 surface")

    skeleton = skeletonize(mask > 0)
    pins = detect_pins(image)
    seeds: list[tuple[int, int, int]] = []
    for label, pin in enumerate(pins, start=1):
        attachment = attach_pin(pin, skeleton)
        pin["attached"] = attachment is not None
        pin["seed_x"] = attachment[0] if attachment else None
        pin["seed_y"] = attachment[1] if attachment else None
        if attachment:
            seeds.append((attachment[1], attachment[0], label))

    labels, _ = geodesic_partition(skeleton, seeds)
    assigned = labels > 0
    conflicts = labels < 0
    unassigned = skeleton & (labels == 0)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0

    route_trees: list[dict[str, object]] = []
    route_tree_pixels: dict[str, list[list[int]]] = {}
    disconnected_tree_count = 0
    for label, pin in enumerate(pins, start=1):
        tree = (labels == label).astype(np.uint8)
        component_count, _ = cv2.connectedComponents(tree, 8)
        tree_components = component_count - 1
        if tree_components > 1:
            disconnected_tree_count += 1
        degree = cv2.filter2D(tree, -1, kernel, borderType=cv2.BORDER_CONSTANT)
        terminal_points = np.argwhere((tree > 0) & (degree == 1))
        junction_points = np.argwhere((tree > 0) & (degree >= 3))
        tree_points = np.argwhere(tree > 0)
        route_tree_pixels[str(label)] = [[int(x), int(y)] for y, x in tree_points]
        route_trees.append(
            {
                "tree_id": label,
                "pin_id": pin["id"],
                "side": pin["side"],
                "pixel_count": int(tree.sum()),
                "component_count": tree_components,
                "terminal_count": int(len(terminal_points)),
                "junction_pixel_count": int(len(junction_points)),
                "terminals": [[int(x), int(y)] for y, x in terminal_points],
            }
        )

    pin_pixel_counts = Counter(labels[assigned].tolist())
    exported_pixels = sum(len(points) for points in route_tree_pixels.values())
    result = {
        "meta": {
            "stage": "PIN_SEEDED_GEODESIC_PARTITION_AUDIT",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "pin_count": len(pins),
            "attached_pin_count": len(seeds),
            "unattached_pin_count": len(pins) - len(seeds),
            "skeleton_pixels": int(skeleton.sum()),
            "assigned_skeleton_pixels": int(assigned.sum()),
            "exported_route_tree_pixels": exported_pixels,
            "route_tree_pixel_export_complete": exported_pixels == int(assigned.sum()),
            "conflict_boundary_pixels": int(conflicts.sum()),
            "unassigned_skeleton_pixels": int(unassigned.sum()),
            "route_tree_count": len(pin_pixel_counts),
            "disconnected_route_tree_count": disconnected_tree_count,
            "min_route_tree_pixels": min(pin_pixel_counts.values(), default=0),
            "max_route_tree_pixels": max(pin_pixel_counts.values(), default=0),
            "partition_status": (
                "PARTITION_COMPLETE_AUDIT_TERMINALS"
                if len(seeds) == len(pins) and len(pin_pixel_counts) == len(pins) and disconnected_tree_count == 0
                else "PARTITION_INCOMPLETE"
            ),
        },
        "pins": pins,
        "route_trees": route_trees,
        "route_tree_pixels": route_tree_pixels,
    }
    (args.out / "pin_partition_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    label_preview = np.zeros((h, w, 3), np.uint8)
    for label in range(1, len(pins) + 1):
        selected = labels == label
        if not selected.any():
            continue
        shade = 80 + ((label * 37) % 175)
        label_preview[selected] = (shade, shade, shade)
    label_preview[conflicts] = (0, 0, 255)
    cv2.imwrite(str(args.out / "pin_partition_mask.png"), label_preview)

    overlay = image.copy()
    overlay[assigned] = cv2.addWeighted(
        overlay[assigned], 0.3, np.full_like(overlay[assigned], 255), 0.7, 0
    )
    overlay[conflicts] = (0, 0, 255)
    for pin in pins:
        color = (0, 255, 0) if pin["attached"] else (0, 0, 255)
        cv2.circle(overlay, (int(pin["x"]), int(pin["y"])), 4, color, 1)
    cv2.imwrite(str(args.out / "pin_partition_overlay.png"), overlay)
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
