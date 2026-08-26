#!/usr/bin/env python3
"""Build a deterministic review queue for unresolved Splash route regions.

The queue is derived only from the reconciliation audit. It never edits route
geometry and never promotes the extraction to canonical. High-chroma, large,
and multi-pin regions are ranked first because they are most likely to contain
real route continuation or true shared junction structure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def priority(region: dict[str, object]) -> tuple[int, float, int, int]:
    classification = str(region["classification"])
    class_rank = {
        "manual-unassigned-review": 0,
        "manual-conflict-review": 1,
        "likely-shared-junction": 2,
        "likely-glow-bridge": 3,
        "likely-isolated-artifact": 4,
        "likely-route-continuation": 0,
    }.get(classification, 5)
    chroma = float(region.get("chroma_support_ratio", 0.0))
    area = int(region.get("area", 0))
    pin_count = int(region.get("touching_pin_count", 0))
    return class_rank, -chroma, -area, -pin_count


def suggested_action(region: dict[str, object]) -> str:
    classification = str(region["classification"])
    chroma = float(region.get("chroma_support_ratio", 0.0))
    area = int(region.get("area", 0))
    pin_count = int(region.get("touching_pin_count", 0))

    if classification == "likely-shared-junction":
        return "verify-shared-junction-against-reference"
    if classification == "likely-glow-bridge":
        return "verify-and-exclude-glow-only-bridge"
    if classification == "likely-isolated-artifact":
        return "verify-and-exclude-isolated-artifact"
    if classification == "manual-unassigned-review":
        if chroma >= 0.70 or area >= 20:
            return "treat-as-probable-route-continuation-until-disproved"
        return "inspect-unassigned-fragment"
    if classification == "manual-conflict-review":
        if pin_count >= 3:
            return "inspect-possible-real-junction"
        return "inspect-two-route-boundary"
    return "manual-review"


def main() -> None:
    args = parse_args()
    payload = json.loads(args.audit.read_text(encoding="utf-8"))
    regions = list(payload.get("regions", []))
    queue = []
    for index, region in enumerate(sorted(regions, key=priority), start=1):
        item = dict(region)
        item["review_rank"] = index
        item["suggested_action"] = suggested_action(region)
        item["decision"] = "PENDING"
        item["review_notes"] = ""
        queue.append(item)

    high_risk = [
        item for item in queue
        if item["suggested_action"] in {
            "treat-as-probable-route-continuation-until-disproved",
            "inspect-possible-real-junction",
            "verify-shared-junction-against-reference",
        }
    ]
    result = {
        "meta": {
            "stage": "UNRESOLVED_REGION_REVIEW_QUEUE",
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "region_count": len(queue),
            "high_risk_region_count": len(high_risk),
            "completion_gate": "all-regions-reviewed-and-decisions-recorded",
        },
        "queue": queue,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
