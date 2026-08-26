#!/usr/bin/env python3
"""Recover bright low-saturation PCB cores and audit per-pin route coverage.

Input is the approved 1672x941 reference image. This stage does not create a
Splash and never promotes a manifest to canonical. It complements the primary
HSV extractor by allowing a chromatic route seed to grow through adjacent
bright anti-aliased/white-hot pixels while remaining inside measured routing
corridors. The result is intended for visual audit and for locating missing
pin-to-route connections.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import cv2
import numpy as np

SIZE = (1672, 941)
CORE = (608, 224, 1041, 632)
EXECUTION_CENTER = (821, 724)
EXECUTION_RADIUS = 58
HUES = {
    "amber": (7, 30),
    "lime": (34, 58),
    "teal": (76, 91),
    "cyan": (92, 118),
    "violet": (126, 160),
}
NEIGHBOURS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1))


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed-saturation", type=int, default=70)
    parser.add_argument("--seed-value", type=int, default=65)
    parser.add_argument("--bridge-value", type=int, default=105)
    parser.add_argument("--bridge-saturation-max", type=int, default=95)
    return parser.parse_args()


def corridor(shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    roi = np.zeros((h, w), np.uint8)
    for left, top, right, bottom in (
        (390, 52, 612, 770),
        (1037, 52, 1270, 770),
        (580, 52, 1090, 228),
        (570, 628, 1100, 790),
    ):
        cv2.rectangle(roi, (left, top), (right, bottom), 255, -1)
    cv2.rectangle(roi, (CORE[0], CORE[1]), (CORE[2], CORE[3]), 0, -1)
    cv2.circle(roi, EXECUTION_CENTER, EXECUTION_RADIUS, 0, -1)
    return roi


def origin_band(shape: tuple[int, int]) -> np.ndarray:
    h, w = shape
    x1, y1, x2, y2 = CORE
    band = np.zeros((h, w), np.uint8)
    cv2.rectangle(band, (594, y1 - 4), (612, y2 + 4), 255, -1)
    cv2.rectangle(band, (1037, y1 - 4), (1055, y2 + 4), 255, -1)
    cv2.rectangle(band, (x1 - 4, 210), (x2 + 4, 230), 255, -1)
    cv2.rectangle(band, (x1 - 4, 626), (x2 + 4, 646), 255, -1)
    return band


def grow(seed: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """8-connected flood fill from seed pixels through allowed route pixels."""
    h, w = seed.shape
    visited = np.zeros_like(seed, np.uint8)
    queue: deque[tuple[int, int]] = deque(map(tuple, np.argwhere(seed > 0)))
    for y, x in queue:
        visited[y, x] = 255
    while queue:
        y, x = queue.popleft()
        for dy, dx in NEIGHBOURS:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and allowed[ny, nx]:
                visited[ny, nx] = 255
                queue.append((ny, nx))
    return visited


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


def pins(image: np.ndarray) -> list[dict[str, int | str | float]]:
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
    result: list[dict[str, int | str | float]] = []
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
            result.append({"id": f"pin-{len(result)+1:03d}", "side": side, "x": x, "y": y, "score": round(float(profile[peak]), 2)})
    return result


def local_coverage(mask: np.ndarray, pin: dict[str, int | str | float]) -> int:
    x, y = int(pin["x"]), int(pin["y"])
    side = str(pin["side"])
    if side == "left":
        window = mask[max(0, y - 5):y + 6, max(0, x - 18):x + 8]
    elif side == "right":
        window = mask[max(0, y - 5):y + 6, x - 8:min(mask.shape[1], x + 19)]
    elif side == "top":
        window = mask[max(0, y - 18):y + 8, max(0, x - 5):x + 6]
    else:
        window = mask[y - 8:min(mask.shape[0], y + 19), max(0, x - 5):x + 6]
    return int((window > 0).sum())


def main() -> None:
    cfg = args()
    cfg.out.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(cfg.image))
    if image is None:
        raise SystemExit(f"Cannot read {cfg.image}")
    h, w = image.shape[:2]
    if (w, h) != SIZE:
        raise SystemExit(f"Reference size changed: {(w, h)} != {SIZE}")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    roi = corridor((h, w))
    band = origin_band((h, w))
    combined = np.zeros((h, w), np.uint8)
    stats: dict[str, object] = {}

    bright_bridge = ((value >= cfg.bridge_value) & (saturation <= cfg.bridge_saturation_max)).astype(np.uint8) * 255
    bright_bridge = cv2.bitwise_and(bright_bridge, roi)

    for color, (lo, hi) in HUES.items():
        chroma = ((hue >= lo) & (hue <= hi) & (saturation >= cfg.seed_saturation) & (value >= cfg.seed_value)).astype(np.uint8) * 255
        chroma = cv2.bitwise_and(chroma, roi)
        seed = cv2.morphologyEx(chroma, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        allowed = cv2.bitwise_or(seed, bright_bridge)
        recovered = grow(seed, allowed)

        count, labels, areas, _ = cv2.connectedComponentsWithStats((recovered > 0).astype(np.uint8), 8)
        keep = np.zeros_like(recovered)
        kept_components = 0
        for label in range(1, count):
            component = labels == label
            if areas[label, cv2.CC_STAT_AREA] < 5:
                continue
            if np.any(component & (band > 0)):
                keep[component] = 255
                kept_components += 1
        combined |= keep
        stats[color] = {"kept_components": kept_components, "pixels": int((keep > 0).sum())}
        cv2.imwrite(str(cfg.out / f"route_mask_{color}.png"), keep)

    detected_pins = pins(image)
    for pin in detected_pins:
        pin["coverage_pixels"] = local_coverage(combined, pin)
        pin["covered"] = int(pin["coverage_pixels"]) >= 3

    coverage_by_side = {
        side: {
            "pins": sum(pin["side"] == side for pin in detected_pins),
            "covered": sum(pin["side"] == side and pin["covered"] for pin in detected_pins),
        }
        for side in ("left", "right", "top", "bottom")
    }
    covered = sum(bool(pin["covered"]) for pin in detected_pins)
    report = {
        "meta": {
            "source": cfg.image.name,
            "size": [w, h],
            "core_bounds": list(CORE),
            "stage": "LUMINANCE_RECOVERY_AUDIT",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "route_pixels": int((combined > 0).sum()),
            "pin_count": len(detected_pins),
            "covered_pin_count": covered,
            "uncovered_pin_count": len(detected_pins) - covered,
            "coverage_by_side": coverage_by_side,
            "color_stats": stats,
        },
        "pins": detected_pins,
    }
    (cfg.out / "reference_route_recovery_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    cv2.imwrite(str(cfg.out / "reference_route_recovered_mask.png"), combined)

    overlay = image.copy()
    overlay[combined > 0] = cv2.addWeighted(overlay[combined > 0], 0.35, np.full_like(overlay[combined > 0], 255), 0.65, 0)
    for pin in detected_pins:
        color = (0, 255, 0) if pin["covered"] else (0, 0, 255)
        cv2.circle(overlay, (int(pin["x"]), int(pin["y"])), 4, color, 1)
    cv2.imwrite(str(cfg.out / "reference_route_recovery_overlay.png"), overlay)
    print(json.dumps(report["meta"], indent=2))


if __name__ == "__main__":
    main()
