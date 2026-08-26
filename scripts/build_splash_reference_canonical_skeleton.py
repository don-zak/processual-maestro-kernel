#!/usr/bin/env python3
"""Build the reviewed canonical Splash skeleton and ownership manifest.

This stage consumes only previously measured pixels and reviewed ownership
semantics. It never generates route geometry. Reconciliation audit files may
omit per-region pixel coordinates, so this builder deterministically reconstructs
the original pin-seeded partition from the recovered reference mask and measured
pin seeds, then re-identifies every conflict/unassigned component by its original
component order. Canonical promotion remains audit-gated until pixel accounting,
connectivity, and visual overlay checks pass.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

REFERENCE_SIZE = (1672, 941)
NEIGHBOURS = (
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),             (0, 1),
    (1, -1),  (1, 0),    (1, 1),
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("recovered_mask", type=Path)
    p.add_argument("partition_audit", type=Path)
    p.add_argument("reconciliation_audit", type=Path)
    p.add_argument("ownership_contract", type=Path)
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def geodesic_partition(
    skeleton: np.ndarray,
    seeds: list[tuple[int, int, int]],
) -> np.ndarray:
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
    return labels


def reconstruct_region_pixels(
    skeleton: np.ndarray,
    pins: list[dict[str, object]],
    reconciliation: dict[str, object],
) -> dict[str, list[list[int]]]:
    seeds: list[tuple[int, int, int]] = []
    for label, pin in enumerate(pins, start=1):
        sx, sy = pin.get("seed_x"), pin.get("seed_y")
        if sx is None or sy is None:
            raise SystemExit(f"Missing measured seed for tree {label}")
        seeds.append((int(sy), int(sx), label))

    labels = geodesic_partition(skeleton, seeds)
    masks = {
        "conflict": (labels < 0).astype(np.uint8),
        "unassigned": (skeleton & (labels == 0)).astype(np.uint8),
    }
    reconstructed: dict[str, list[list[int]]] = {}
    for kind, region_mask in masks.items():
        count, components, stats, _ = cv2.connectedComponentsWithStats(region_mask, 8)
        index = 0
        for component_label in range(1, count):
            area = int(stats[component_label, cv2.CC_STAT_AREA])
            if area == 0:
                continue
            index += 1
            region_id = f"{kind}-{index:03d}"
            ys, xs = np.where(components == component_label)
            reconstructed[region_id] = [[int(x), int(y)] for y, x in zip(ys, xs)]

    audit_regions = {str(r["id"]): r for r in reconciliation.get("regions", [])}
    missing = sorted(set(audit_regions) - set(reconstructed))
    extra = sorted(set(reconstructed) - set(audit_regions))
    if missing or extra:
        raise SystemExit(
            "Reconstructed reconciliation regions differ from the reviewed audit: "
            f"missing={missing}, extra={extra}"
        )

    for region_id, audit_region in audit_regions.items():
        pixels = reconstructed[region_id]
        expected_area = int(audit_region.get("area", len(pixels)))
        if len(pixels) != expected_area:
            raise SystemExit(
                f"Region {region_id} area drift: reconstructed={len(pixels)} reviewed={expected_area}"
            )
    return reconstructed


def region_pixels(
    regions: dict[str, dict[str, object]],
    reconstructed: dict[str, list[list[int]]],
    region_id: str,
) -> list[list[int]]:
    region = regions.get(region_id)
    if region is None:
        raise SystemExit(f"Unknown reconciliation region: {region_id}")
    serialized = region.get("pixels")
    pixels = (
        [[int(x), int(y)] for x, y in serialized]
        if isinstance(serialized, list) and serialized
        else reconstructed.get(region_id, [])
    )
    if not pixels:
        raise SystemExit(f"No measured pixels available for reviewed region {region_id}")
    expected_area = int(region.get("area", len(pixels)))
    if len(pixels) != expected_area:
        raise SystemExit(
            f"Reviewed region {region_id} pixel count mismatch: pixels={len(pixels)} area={expected_area}"
        )
    return pixels


def add_pixels(target: set[tuple[int, int]], pixels: list[list[int]]) -> None:
    for x, y in pixels:
        target.add((int(x), int(y)))


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    mask = cv2.imread(str(args.recovered_mask), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise SystemExit(f"Cannot read recovered reference mask: {args.recovered_mask}")
    h, w = mask.shape
    if (w, h) != REFERENCE_SIZE:
        raise SystemExit(f"Recovered mask must be {REFERENCE_SIZE}, got {(w, h)}")
    skeleton = skeletonize(mask > 0)

    partition = json.loads(args.partition_audit.read_text(encoding="utf-8"))
    reconciliation = json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    contract = json.loads(args.ownership_contract.read_text(encoding="utf-8"))

    tree_payload = partition.get("route_tree_pixels")
    pins = partition.get("pins", [])
    if not isinstance(tree_payload, dict):
        raise SystemExit("partition audit lacks route_tree_pixels")
    if len(pins) != 125:
        raise SystemExit(f"Expected 125 measured pins, found {len(pins)}")

    reconstructed = reconstruct_region_pixels(skeleton, pins, reconciliation)
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
        if not isinstance(pixels, list) or not pixels:
            raise SystemExit(f"Missing pixel ownership for tree {tree_id}")
        trees[tree_id] = {(int(x), int(y)) for x, y in pixels}

    attachment_records: list[dict[str, object]] = []
    for item in unique:
        region_id = str(item["region"])
        target = int(item["target_tree"])
        pixels = region_pixels(regions, reconstructed, region_id)
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
        pixels = region_pixels(regions, reconstructed, region_id)
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
        pixels = region_pixels(regions, reconstructed, region_id)
        add_pixels(unowned_pixels, pixels)
        unowned_records.append({
            "region": region_id,
            "reason": item.get("reason"),
            "pixel_count": len(pixels),
            "pixels": pixels,
        })

    owned_union: set[tuple[int, int]] = set()
    tree_records: list[dict[str, object]] = []
    disconnected_tree_count = 0
    for tree_id in range(1, 126):
        pixels = trees[tree_id]
        owned_union.update(pixels)
        tree_mask = np.zeros((h, w), np.uint8)
        for x, y in pixels:
            tree_mask[y, x] = 1
        component_count, _ = cv2.connectedComponents(tree_mask, 8)
        components = component_count - 1
        if components != 1:
            disconnected_tree_count += 1
        pin = pins[tree_id - 1]
        tree_records.append({
            "tree_id": tree_id,
            "pin_id": pin.get("id"),
            "side": pin.get("side"),
            "pin": [int(pin["x"]), int(pin["y"])],
            "seed": [int(pin["seed_x"]), int(pin["seed_y"])],
            "pixel_count": len(pixels),
            "component_count": components,
            "pixels": [[x, y] for x, y in sorted(pixels, key=lambda p: (p[1], p[0]))],
        })

    overlap_owned_shared = owned_union & shared_pixels
    overlap_owned_unowned = owned_union & unowned_pixels
    overlap_shared_unowned = shared_pixels & unowned_pixels
    if overlap_owned_unowned or overlap_shared_unowned:
        raise SystemExit("Preserved unowned geometry overlaps owned/shared canonical geometry")

    canonical_pixels = owned_union | shared_pixels | unowned_pixels
    output = np.zeros((h, w), np.uint8)
    for x, y in canonical_pixels:
        if not (0 <= x < w and 0 <= y < h):
            raise SystemExit(f"Canonical pixel outside reference bounds: {(x, y)}")
        output[y, x] = 255

    manifest = {
        "meta": {
            "stage": "CANONICAL_SKELETON_CANDIDATE",
            "source_of_truth": "approved pivot reference image",
            "reference_size": list(REFERENCE_SIZE),
            "canonical_candidate": True,
            "canonical_promoted": False,
            "splash_reconstruction_allowed": False,
            "route_tree_count": 125,
            "disconnected_route_tree_count": disconnected_tree_count,
            "unique_attachment_count": len(attachment_records),
            "shared_geometry_region_count": len(shared_records),
            "preserved_unowned_region_count": len(unowned_records),
            "reconstructed_review_region_count": len(reconstructed),
            "owned_pixel_count": len(owned_union),
            "shared_pixel_count": len(shared_pixels),
            "preserved_unowned_pixel_count": len(unowned_pixels),
            "canonical_union_pixel_count": len(canonical_pixels),
            "owned_shared_overlap_pixel_count": len(overlap_owned_shared),
            "ownership_ambiguity_count": 0,
            "promotion_gate": "zero disconnected route trees + pixel-accounting + visual-overlay audit",
        },
        "route_trees": tree_records,
        "unique_attachments": attachment_records,
        "shared_geometry": shared_records,
        "preserved_unowned_geometry": unowned_records,
    }

    cv2.imwrite(str(args.out / "canonical_skeleton_candidate.png"), output)
    (args.out / "canonical_route_manifest_candidate.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest["meta"], indent=2))


if __name__ == "__main__":
    main()
