#!/usr/bin/env python3
"""Build the reviewed canonical Splash skeleton and ownership manifest.

This stage consumes only previously measured pixels and reviewed ownership
semantics. It never generates route geometry. The output contains 125 pin-owned
route trees plus explicit shared geometry and preserved unowned geometry.
Canonical promotion remains audit-gated: the produced manifest is a candidate
until pixel accounting and connectivity checks pass.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

REFERENCE_SIZE = (1672, 941)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("partition_audit", type=Path)
    p.add_argument("reconciliation_audit", type=Path)
    p.add_argument("ownership_contract", type=Path)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def region_pixels(regions: dict[str, dict[str, object]], region_id: str) -> list[list[int]]:
    region = regions.get(region_id)
    if region is None:
        raise SystemExit(f"Unknown reconciliation region: {region_id}")
    return [[int(x), int(y)] for x, y in region.get("pixels", [])]


def add_pixels(target: set[tuple[int, int]], pixels: list[list[int]]) -> None:
    for x, y in pixels:
        target.add((int(x), int(y)))


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    partition = json.loads(args.partition_audit.read_text(encoding="utf-8"))
    reconciliation = json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    contract = json.loads(args.ownership_contract.read_text(encoding="utf-8"))

    tree_payload = partition.get("route_tree_pixels")
    pins = partition.get("pins", [])
    if not isinstance(tree_payload, dict):
        raise SystemExit("partition audit lacks route_tree_pixels")
    if len(pins) != 125:
        raise SystemExit(f"Expected 125 measured pins, found {len(pins)}")

    regions = {str(r["id"]): r for r in reconciliation.get("regions", [])}
    ownership = contract.get("latest_measured_audit", {}).get("ownership_resolution", {})
    unique = ownership.get("unique_owner_regions", [])
    shared = ownership.get("shared_geometry_regions", [])
    unowned = ownership.get("preserved_unowned_regions", [])
    if int(ownership.get("remaining_ambiguous_fragment_count", -1)) != 0:
        raise SystemExit("Ownership ambiguity is not closed")

    trees: dict[int, set[tuple[int, int]]] = {}
    for tree_id in range(1, 126):
        pixels = tree_payload.get(str(tree_id))
        if not isinstance(pixels, list):
            raise SystemExit(f"Missing pixel ownership for tree {tree_id}")
        trees[tree_id] = {(int(x), int(y)) for x, y in pixels}

    attachment_records: list[dict[str, object]] = []
    for item in unique:
        region_id = str(item["region"])
        target = int(item["target_tree"])
        pixels = region_pixels(regions, region_id)
        add_pixels(trees[target], pixels)
        attachment_records.append({
            "region": region_id,
            "target_tree": target,
            "stage": item.get("stage"),
            "pixel_count": len(pixels),
        })

    shared_records: list[dict[str, object]] = []
    shared_pixels: set[tuple[int, int]] = set()
    for item in shared:
        region_id = str(item["region"])
        targets = [int(v) for v in item.get("target_trees", [])]
        if len(targets) < 2:
            raise SystemExit(f"Shared geometry {region_id} has fewer than two target trees")
        pixels = region_pixels(regions, region_id)
        add_pixels(shared_pixels, pixels)
        shared_records.append({
            "region": region_id,
            "target_trees": targets,
            "pixel_count": len(pixels),
            "pixels": pixels,
        })

    unowned_records: list[dict[str, object]] = []
    unowned_pixels: set[tuple[int, int]] = set()
    for item in unowned:
        region_id = str(item["region"])
        pixels = region_pixels(regions, region_id)
        add_pixels(unowned_pixels, pixels)
        unowned_records.append({
            "region": region_id,
            "reason": item.get("reason"),
            "pixel_count": len(pixels),
            "pixels": pixels,
        })

    owned_union: set[tuple[int, int]] = set()
    tree_records: list[dict[str, object]] = []
    for tree_id in range(1, 126):
        pixels = trees[tree_id]
        owned_union.update(pixels)
        pin = pins[tree_id - 1]
        tree_records.append({
            "tree_id": tree_id,
            "pin_id": pin.get("id"),
            "side": pin.get("side"),
            "pin": [int(pin["x"]), int(pin["y"])],
            "seed": [int(pin["seed_x"]), int(pin["seed_y"])],
            "pixel_count": len(pixels),
            "pixels": [[x, y] for x, y in sorted(pixels, key=lambda p: (p[1], p[0]))],
        })

    overlap_owned_shared = owned_union & shared_pixels
    overlap_owned_unowned = owned_union & unowned_pixels
    overlap_shared_unowned = shared_pixels & unowned_pixels
    if overlap_owned_unowned or overlap_shared_unowned:
        raise SystemExit("Preserved unowned geometry overlaps owned/shared canonical geometry")

    canonical_pixels = owned_union | shared_pixels | unowned_pixels
    w, h = REFERENCE_SIZE
    skeleton = np.zeros((h, w), np.uint8)
    for x, y in canonical_pixels:
        if not (0 <= x < w and 0 <= y < h):
            raise SystemExit(f"Canonical pixel outside reference bounds: {(x, y)}")
        skeleton[y, x] = 255

    manifest = {
        "meta": {
            "stage": "CANONICAL_SKELETON_CANDIDATE",
            "source_of_truth": "approved pivot reference image",
            "reference_size": list(REFERENCE_SIZE),
            "canonical_candidate": True,
            "canonical_promoted": False,
            "splash_reconstruction_allowed": False,
            "route_tree_count": 125,
            "unique_attachment_count": len(attachment_records),
            "shared_geometry_region_count": len(shared_records),
            "preserved_unowned_region_count": len(unowned_records),
            "owned_pixel_count": len(owned_union),
            "shared_pixel_count": len(shared_pixels),
            "preserved_unowned_pixel_count": len(unowned_pixels),
            "canonical_union_pixel_count": len(canonical_pixels),
            "owned_shared_overlap_pixel_count": len(overlap_owned_shared),
            "ownership_ambiguity_count": 0,
            "promotion_gate": "pixel-accounting + connectivity + visual-overlay audit",
        },
        "route_trees": tree_records,
        "unique_attachments": attachment_records,
        "shared_geometry": shared_records,
        "preserved_unowned_geometry": unowned_records,
    }

    cv2.imwrite(str(args.out / "canonical_skeleton_candidate.png"), skeleton)
    (args.out / "canonical_route_manifest_candidate.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest["meta"], indent=2))


if __name__ == "__main__":
    main()
