#!/usr/bin/env python3
"""Classify unresolved pixels after pin-seeded geodesic partitioning.

This audit stage does not modify or invent routing. It re-runs the same pin-seeded
partition over the recovered reference skeleton, then classifies the remaining
conflict/unassigned pixels into small connected regions so each can be reviewed as
one of: likely shared junction, likely glow bridge, likely continuation gap, or
isolated artifact. Canonical promotion remains prohibited.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict, deque
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
        i for i in range(1, len(profile) - 1)
        if profile[i] >= min_height and profile[i] >= profile[i - 1] and profile[i] > profile[i + 1]
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
            pins.append({"id": f"pin-{len(pins)+1:03d}", "side": side, "x": x, "y": y})
    return pins


def outward_window(pin: dict[str, int | str | float], shape: tuple[int, int]) -> tuple[slice, slice]:
    h, w = shape
    x, y = int(pin["x"]), int(pin["y"])
    side = str(pin["side"])
    if side == "left":
        return slice(max(0, y-6), min(h, y+7)), slice(max(0, x-30), min(w, x+10))
    if side == "right":
        return slice(max(0, y-6), min(h, y+7)), slice(max(0, x-10), min(w, x+31))
    if side == "top":
        return slice(max(0, y-30), min(h, y+10)), slice(max(0, x-6), min(w, x+7))
    return slice(max(0, y-10), min(h, y+31)), slice(max(0, x-6), min(w, x+7))


def attach_pin(pin: dict[str, int | str | float], skeleton: np.ndarray) -> tuple[int, int] | None:
    ys, xs = outward_window(pin, skeleton.shape)
    py, px = np.where(skeleton[ys, xs])
    if len(px) == 0:
        return None
    ox, oy = int(pin["x"]), int(pin["y"])
    candidates = [(xs.start + int(x), ys.start + int(y)) for y, x in zip(py, px)]
    return min(candidates, key=lambda p: (p[0]-ox)**2 + (p[1]-oy)**2)


def partition(skeleton: np.ndarray, seeds: list[tuple[int, int, int]]) -> np.ndarray:
    h, w = skeleton.shape
    inf = np.iinfo(np.int32).max
    dist = np.full((h, w), inf, np.int32)
    labels = np.zeros((h, w), np.int32)
    queue: deque[tuple[int, int, int]] = deque()
    for y, x, label in seeds:
        dist[y, x] = 0
        labels[y, x] = label
        queue.append((y, x, label))
    while queue:
        y, x, label = queue.popleft()
        if labels[y, x] != label:
            continue
        nd = dist[y, x] + 1
        for dy, dx in NEIGHBOURS:
            ny, nx = y + dy, x + dx
            if not (0 <= ny < h and 0 <= nx < w and skeleton[ny, nx]):
                continue
            if nd < dist[ny, nx]:
                dist[ny, nx] = nd
                labels[ny, nx] = label
                queue.append((ny, nx, label))
            elif nd == dist[ny, nx] and labels[ny, nx] not in (label, -1):
                labels[ny, nx] = -1
    return labels


def touching_labels(component: np.ndarray, labels: np.ndarray) -> set[int]:
    dilated = cv2.dilate(component.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=1) > 0
    return {int(v) for v in np.unique(labels[dilated]) if int(v) > 0}


def classify_region(kind: str, area: int, degree_values: np.ndarray, labels_touching: set[int], chroma_ratio: float) -> str:
    max_degree = int(degree_values.max()) if degree_values.size else 0
    if kind == "conflict":
        if len(labels_touching) >= 3 and max_degree >= 3 and area <= 12:
            return "likely-shared-junction"
        if len(labels_touching) == 2 and max_degree <= 2:
            return "likely-glow-bridge"
        return "manual-conflict-review"
    if len(labels_touching) == 1 and chroma_ratio >= 0.45:
        return "likely-route-continuation"
    if len(labels_touching) == 0 and chroma_ratio < 0.25:
        return "likely-isolated-artifact"
    return "manual-unassigned-review"


def region_records(mask: np.ndarray, labels: np.ndarray, degree: np.ndarray, chroma: np.ndarray, kind: str) -> list[dict[str, object]]:
    count, cc, stats, centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    records: list[dict[str, object]] = []
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area == 0:
            continue
        component = cc == label
        ys, xs = np.where(component)
        touched = touching_labels(component, labels)
        chroma_ratio = float((chroma[component] > 0).sum()) / area
        degree_values = degree[component]
        records.append({
            "id": f"{kind}-{len(records)+1:03d}",
            "kind": kind,
            "area": area,
            "bbox": [
                int(stats[label, cv2.CC_STAT_LEFT]),
                int(stats[label, cv2.CC_STAT_TOP]),
                int(stats[label, cv2.CC_STAT_WIDTH]),
                int(stats[label, cv2.CC_STAT_HEIGHT]),
            ],
            "centroid": [round(float(centroids[label][0]), 1), round(float(centroids[label][1]), 1)],
            "touching_pin_labels": sorted(touched),
            "touching_pin_count": len(touched),
            "max_local_degree": int(degree_values.max()) if degree_values.size else 0,
            "mean_local_degree": round(float(degree_values.mean()), 2) if degree_values.size else 0.0,
            "chroma_support_ratio": round(chroma_ratio, 3),
            "classification": classify_region(kind, area, degree_values, touched, chroma_ratio),
            "pixels": [[int(x), int(y)] for y, x in zip(ys, xs)],
        })
    return records


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(args.reference))
    mask = cv2.imread(str(args.recovered_mask), cv2.IMREAD_GRAYSCALE)
    if image is None or mask is None:
        raise SystemExit("Reference image or recovered mask could not be read")
    h, w = image.shape[:2]
    if (w, h) != REFERENCE_SIZE or mask.shape != (h, w):
        raise SystemExit("Reference/mask geometry mismatch")

    skeleton = skeletonize(mask > 0)
    pins = detect_pins(image)
    seeds: list[tuple[int, int, int]] = []
    for label, pin in enumerate(pins, start=1):
        point = attach_pin(pin, skeleton)
        if point:
            seeds.append((point[1], point[0], label))

    labels = partition(skeleton, seeds)
    conflict = labels < 0
    unassigned = skeleton & (labels == 0)
    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    degree = cv2.filter2D(skeleton.astype(np.uint8), -1, kernel, borderType=cv2.BORDER_CONSTANT)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, saturation, value = cv2.split(hsv)
    chroma = ((saturation >= 55) & (value >= 55)).astype(np.uint8)

    regions = region_records(conflict, labels, degree, chroma, "conflict")
    regions += region_records(unassigned, labels, degree, chroma, "unassigned")
    counts = Counter(str(region["classification"]) for region in regions)

    result = {
        "meta": {
            "stage": "UNRESOLVED_PARTITION_RECONCILIATION_AUDIT",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "pin_count": len(pins),
            "attached_pin_count": len(seeds),
            "conflict_pixels": int(conflict.sum()),
            "unassigned_pixels": int(unassigned.sum()),
            "unresolved_pixels": int(conflict.sum() + unassigned.sum()),
            "region_count": len(regions),
            "classification_counts": dict(counts),
            "next_gate": "manual-review-regions-then-canonical-graph",
        },
        "regions": regions,
    }
    (args.out / "partition_reconciliation_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    overlay = image.copy()
    overlay[conflict] = (0, 0, 255)
    overlay[unassigned] = (255, 0, 255)
    cv2.imwrite(str(args.out / "partition_reconciliation_overlay.png"), overlay)
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
