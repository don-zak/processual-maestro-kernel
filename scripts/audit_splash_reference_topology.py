#!/usr/bin/env python3
"""Audit recovered Splash route topology before canonical promotion.

The recovered luminance mask can cover every central-core pin while still
accidentally merging neighboring PCB lanes through glow. This audit skeletonizes
the recovered mask, attaches each measured core pin to the nearest outward
skeleton pixel, and reports connected components that contain more than one pin.
It never edits route geometry and cannot promote a manifest to canonical.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

REFERENCE_SIZE = (1672, 941)
CORE = (608, 224, 1041, 632)


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


def attach_pin(pin: dict[str, int | str | float], skeleton: np.ndarray, labels: np.ndarray) -> dict[str, object]:
    y_slice, x_slice = outward_window(pin, skeleton.shape)
    ys, xs = np.where(skeleton[y_slice, x_slice])
    record = dict(pin)
    if len(xs) == 0:
        record.update({"attached": False, "component": None, "skeleton_x": None, "skeleton_y": None})
        return record

    origin_x, origin_y = int(pin["x"]), int(pin["y"])
    candidates = [
        (x_slice.start + int(x), y_slice.start + int(y))
        for y, x in zip(ys, xs)
    ]
    selected_x, selected_y = min(
        candidates,
        key=lambda point: (point[0] - origin_x) ** 2 + (point[1] - origin_y) ** 2,
    )
    record.update(
        {
            "attached": True,
            "component": int(labels[selected_y, selected_x]),
            "skeleton_x": selected_x,
            "skeleton_y": selected_y,
        }
    )
    return record


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
    component_count, labels = cv2.connectedComponents(skeleton.astype(np.uint8), 8)

    kernel = np.ones((3, 3), np.uint8)
    kernel[1, 1] = 0
    degree = cv2.filter2D(skeleton.astype(np.uint8), -1, kernel, borderType=cv2.BORDER_CONSTANT)
    terminals = skeleton & (degree == 1)

    pins = [attach_pin(pin, skeleton, labels) for pin in detect_pins(image)]
    by_component: dict[int, list[dict[str, object]]] = defaultdict(list)
    for pin in pins:
        if pin["attached"]:
            by_component[int(pin["component"])].append(pin)

    components: list[dict[str, object]] = []
    for component, attached_pins in sorted(by_component.items()):
        component_mask = labels == component
        components.append(
            {
                "component": component,
                "pin_count": len(attached_pins),
                "pin_ids": [str(pin["id"]) for pin in attached_pins],
                "skeleton_pixels": int(component_mask.sum()),
                "terminal_pixels": int((terminals & component_mask).sum()),
                "requires_merge_review": len(attached_pins) > 1,
            }
        )

    attached_count = sum(bool(pin["attached"]) for pin in pins)
    multi_pin = [component for component in components if component["requires_merge_review"]]
    max_pins = max((int(component["pin_count"]) for component in components), default=0)
    result = {
        "meta": {
            "stage": "RECOVERED_MASK_TOPOLOGY_AUDIT",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "pin_count": len(pins),
            "attached_pin_count": attached_count,
            "unattached_pin_count": len(pins) - attached_count,
            "skeleton_component_count": component_count - 1,
            "pin_touched_component_count": len(components),
            "multi_pin_component_count": len(multi_pin),
            "max_pins_in_one_component": max_pins,
            "topology_status": "MERGE_RECONCILIATION_REQUIRED" if multi_pin else "NO_MULTI_PIN_MERGES_DETECTED",
        },
        "pins": pins,
        "pin_components": components,
    }
    (args.out / "topology_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    cv2.imwrite(str(args.out / "recovered_route_skeleton.png"), skeleton.astype(np.uint8) * 255)

    overlay = image.copy()
    overlay[skeleton] = (255, 255, 255)
    for pin in pins:
        center = (int(pin["x"]), int(pin["y"]))
        if not pin["attached"]:
            color = (0, 0, 255)
        else:
            component_pin_count = len(by_component[int(pin["component"])])
            color = (0, 165, 255) if component_pin_count > 1 else (0, 255, 0)
        cv2.circle(overlay, center, 4, color, 1)
    cv2.imwrite(str(args.out / "topology_audit_overlay.png"), overlay)
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
