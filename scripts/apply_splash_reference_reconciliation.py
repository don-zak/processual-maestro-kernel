#!/usr/bin/env python3
"""Apply reviewed reconciliation decisions to an audit skeleton.

This tool is deliberately conservative: it may remove only regions explicitly
marked EXCLUDE_ARTIFACT. ATTACH_CONTINUATION and MERGE_AS_JUNCTION decisions
preserve the recovered geometry and are recorded as ownership metadata rather
than inventing pixels. PENDING decisions are never modified. The resulting mask
is still non-canonical until all review decisions are complete.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize


ALLOWED_DECISIONS = {
    "EXCLUDE_ARTIFACT",
    "ATTACH_CONTINUATION",
    "MERGE_AS_JUNCTION",
    "KEEP",
    "PENDING_MANUAL",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("recovered_mask", type=Path)
    parser.add_argument("reconciliation_audit", type=Path)
    parser.add_argument("decisions", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    mask = cv2.imread(str(args.recovered_mask), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise SystemExit(f"Cannot read recovered mask: {args.recovered_mask}")
    skeleton = skeletonize(mask > 0)

    audit = json.loads(args.reconciliation_audit.read_text(encoding="utf-8"))
    decisions_payload = json.loads(args.decisions.read_text(encoding="utf-8"))
    regions = {str(region["id"]): region for region in audit.get("regions", [])}
    decisions = {str(item["region"]): item for item in decisions_payload.get("decisions", [])}

    unknown = sorted(set(decisions) - set(regions))
    if unknown:
        raise SystemExit(f"Decision file references unknown regions: {unknown}")

    corrected = skeleton.copy()
    ownership: list[dict[str, object]] = []
    removed_pixels = 0
    attached_pixels = 0
    pending_pixels = 0

    for region_id, item in decisions.items():
        decision = str(item["decision"])
        if decision not in ALLOWED_DECISIONS:
            raise SystemExit(f"Unsupported decision {decision!r} for {region_id}")
        region = regions[region_id]
        pixels = [(int(x), int(y)) for x, y in region.get("pixels", [])]

        if decision == "EXCLUDE_ARTIFACT":
            for x, y in pixels:
                corrected[y, x] = False
            removed_pixels += len(pixels)
        elif decision == "ATTACH_CONTINUATION":
            if "target_tree" not in item:
                raise SystemExit(f"ATTACH_CONTINUATION lacks target_tree for {region_id}")
            attached_pixels += len(pixels)
            ownership.append(
                {
                    "region": region_id,
                    "decision": decision,
                    "target_tree": int(item["target_tree"]),
                    "pixels": [[x, y] for x, y in pixels],
                }
            )
        elif decision == "MERGE_AS_JUNCTION":
            targets = item.get("target_trees")
            if not isinstance(targets, list) or len(targets) < 2:
                raise SystemExit(f"MERGE_AS_JUNCTION lacks target_trees for {region_id}")
            ownership.append(
                {
                    "region": region_id,
                    "decision": decision,
                    "target_trees": [int(value) for value in targets],
                    "pixels": [[x, y] for x, y in pixels],
                }
            )
        elif decision == "PENDING_MANUAL":
            pending_pixels += len(pixels)

    decision_counts: dict[str, int] = {}
    for item in decisions.values():
        key = str(item["decision"])
        decision_counts[key] = decision_counts.get(key, 0) + 1

    unresolved_regions = [
        region
        for region_id, region in regions.items()
        if region_id not in decisions or decisions.get(region_id, {}).get("decision") == "PENDING_MANUAL"
    ]
    result = {
        "meta": {
            "stage": "REVIEWED_RECONCILIATION_APPLICATION",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "input_skeleton_pixels": int(skeleton.sum()),
            "corrected_skeleton_pixels": int(corrected.sum()),
            "removed_artifact_pixels": removed_pixels,
            "attached_continuation_pixels": attached_pixels,
            "pending_decision_pixels": pending_pixels,
            "decision_counts": decision_counts,
            "remaining_unresolved_region_count": len(unresolved_regions),
            "completion_gate": "zero-pending-and-all-conflict-regions-reviewed",
        },
        "ownership": ownership,
        "remaining_unresolved_regions": [str(region["id"]) for region in unresolved_regions],
    }

    cv2.imwrite(str(args.out / "reviewed_corrected_skeleton.png"), corrected.astype(np.uint8) * 255)
    (args.out / "reviewed_reconciliation_application.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
