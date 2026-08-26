#!/usr/bin/env python3
"""Tile-by-tile audit for the recovered Splash reference routing mask.

The script compares the recovered route mask to a permissive chromatic candidate
surface from the approved reference image. It does not alter route geometry and
cannot promote a manifest to canonical. Its purpose is to locate regions that
need manual false-positive/false-negative reconciliation before graph promotion.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

REFERENCE_SIZE = (1672, 941)

TILES = {
    "left-top": (390, 52, 612, 224),
    "left-upper": (390, 224, 612, 360),
    "left-lower": (390, 360, 612, 500),
    "left-bottom": (390, 500, 612, 770),
    "top-left": (580, 52, 760, 228),
    "top-mid": (740, 52, 920, 228),
    "top-right": (900, 52, 1090, 228),
    "right-top": (1037, 52, 1270, 224),
    "right-upper": (1037, 224, 1270, 360),
    "right-lower": (1037, 360, 1270, 500),
    "right-bottom": (1037, 500, 1270, 770),
    "bottom-left": (570, 628, 760, 790),
    "bottom-mid": (740, 628, 930, 790),
    "bottom-right": (910, 628, 1100, 790),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("recovered_mask", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


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

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    _, saturation, value = cv2.split(hsv)
    candidate = ((saturation >= 35) & (value >= 45)).astype(np.uint8) * 255

    records: list[dict[str, object]] = []
    thumbnails: list[np.ndarray] = []
    for name, (x1, y1, x2, y2) in TILES.items():
        tile_mask = mask[y1:y2, x1:x2]
        tile_candidate = candidate[y1:y2, x1:x2]
        area = max(1, (y2 - y1) * (x2 - x1))
        route_pixels = int((tile_mask > 0).sum())
        candidate_pixels = int((tile_candidate > 0).sum())
        density = route_pixels / area
        candidate_ratio = route_pixels / max(1, candidate_pixels)

        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            (tile_mask > 0).astype(np.uint8), 8
        )
        components: list[int] = []
        border_spanning = 0
        for label in range(1, count):
            component_area = int(stats[label, cv2.CC_STAT_AREA])
            if component_area < 3:
                continue
            components.append(component_area)
            component = labels == label
            touches = sum(
                (
                    bool(component[0, :].any()),
                    bool(component[-1, :].any()),
                    bool(component[:, 0].any()),
                    bool(component[:, -1].any()),
                )
            )
            if touches >= 3:
                border_spanning += 1

        status = "review"
        if density > 0.16 or border_spanning:
            status = "possible-overgrowth"
        if candidate_ratio < 0.18:
            status = "possible-undercoverage"

        records.append(
            {
                "tile": name,
                "bounds": [x1, y1, x2, y2],
                "route_pixels": route_pixels,
                "candidate_pixels": candidate_pixels,
                "density": round(density, 4),
                "route_candidate_ratio": round(candidate_ratio, 3),
                "components": len(components),
                "largest_component": max(components) if components else 0,
                "border_spanning_components": border_spanning,
                "status": status,
            }
        )

        crop = image[y1:y2, x1:x2].copy()
        selected = tile_mask > 0
        crop[selected] = cv2.addWeighted(
            crop[selected], 0.25, np.full_like(crop[selected], 255), 0.75, 0
        )
        cv2.imwrite(str(args.out / f"{name}.png"), crop)
        thumb = cv2.resize(crop, (300, 220))
        cv2.putText(thumb, name, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(thumb, status, (8, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1, cv2.LINE_AA)
        thumbnails.append(thumb)

    rows: list[np.ndarray] = []
    for index in range(0, len(thumbnails), 3):
        row = thumbnails[index:index + 3]
        while len(row) < 3:
            row.append(np.zeros_like(thumbnails[0]))
        rows.append(np.hstack(row))
    cv2.imwrite(str(args.out / "tile_audit_contact_sheet.png"), np.vstack(rows))

    result = {
        "meta": {
            "stage": "TILE_BY_TILE_ROUTE_AUDIT",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "tile_count": len(records),
            "status_counts": dict(Counter(str(record["status"]) for record in records)),
        },
        "tiles": records,
    }
    (args.out / "tile_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
