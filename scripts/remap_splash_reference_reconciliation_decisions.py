#!/usr/bin/env python3
"""Remap reviewed reconciliation semantics after reference-only recovery.

The source and target reconciliation audits must both serialize exact pixels.
Residual target regions are accepted only when their pixel sets are identical to
one reviewed source region. Source regions that disappear are reported as
absorbed by the new pin partition. New or changed residual geometry is a hard
failure and requires visual review instead of automatic semantic carry-forward.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PENDING = {"PENDING_MANUAL", "KEEP"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("source_audit", type=Path)
    p.add_argument("target_audit", type=Path)
    p.add_argument("decisions", type=Path, nargs="+")
    p.add_argument("--out", type=Path, required=True)
    return p.parse_args()


def pixel_key(region: dict[str, object]) -> frozenset[tuple[int, int]]:
    pixels = region.get("pixels")
    if not isinstance(pixels, list) or not pixels:
        raise SystemExit(f"Region {region.get('id')} lacks serialized pixels")
    return frozenset((int(x), int(y)) for x, y in pixels)


def load_decisions(paths: list[Path]) -> tuple[dict[str, dict[str, object]], dict[str, list[str]]]:
    merged: dict[str, dict[str, object]] = {}
    provenance: dict[str, list[str]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("decisions", []):
            region = str(item["region"])
            prior = merged.get(region)
            if prior is None:
                merged[region] = dict(item)
                provenance[region] = [path.name]
                continue
            prior_decision = str(prior.get("decision"))
            new_decision = str(item.get("decision"))
            if prior_decision in PENDING and new_decision not in PENDING:
                merged[region] = dict(item)
                provenance[region].append(path.name)
            elif new_decision in PENDING and prior_decision not in PENDING:
                provenance[region].append(path.name)
            elif prior == item:
                provenance[region].append(path.name)
            elif prior_decision == new_decision and prior_decision == "EXCLUDE_ARTIFACT":
                provenance[region].append(path.name)
            else:
                raise SystemExit(
                    f"Conflicting non-pending decisions for {region}: "
                    f"{prior_decision} vs {new_decision}"
                )
    return merged, provenance


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    source = json.loads(args.source_audit.read_text(encoding="utf-8"))
    target = json.loads(args.target_audit.read_text(encoding="utf-8"))
    decisions, provenance = load_decisions(args.decisions)

    source_regions = {str(r["id"]): r for r in source.get("regions", [])}
    target_regions = {str(r["id"]): r for r in target.get("regions", [])}
    source_by_pixels: dict[frozenset[tuple[int, int]], str] = {}
    for region_id, region in source_regions.items():
        key = pixel_key(region)
        if key in source_by_pixels:
            raise SystemExit(f"Duplicate source pixel set: {region_id} / {source_by_pixels[key]}")
        source_by_pixels[key] = region_id

    remapped: list[dict[str, object]] = []
    matched_source: set[str] = set()
    changed_target: list[str] = []
    for target_id, region in target_regions.items():
        source_id = source_by_pixels.get(pixel_key(region))
        if source_id is None:
            changed_target.append(target_id)
            continue
        matched_source.add(source_id)
        decision = decisions.get(source_id)
        if decision is None:
            raise SystemExit(f"Reviewed source region {source_id} has no merged decision")
        carried = dict(decision)
        carried["region"] = target_id
        carried["source_region"] = source_id
        carried["decision_sources"] = provenance.get(source_id, [])
        remapped.append(carried)

    if changed_target:
        raise SystemExit(
            "Target repartition contains new/changed residual geometry requiring review: "
            + ", ".join(changed_target)
        )

    absorbed = sorted(set(source_regions) - matched_source)
    unresolved = [
        item for item in remapped
        if str(item.get("decision")) in PENDING
    ]
    result = {
        "meta": {
            "stage": "RECONCILIATION_DECISION_REMAP_AFTER_REFERENCE_RECOVERY",
            "source_region_count": len(source_regions),
            "target_region_count": len(target_regions),
            "pixel_identical_target_region_count": len(remapped),
            "new_or_changed_target_region_count": 0,
            "absorbed_source_region_count": len(absorbed),
            "pending_or_keep_region_count": len(unresolved),
            "canonical": False,
            "splash_reconstruction_allowed": False,
            "next_gate": "apply explicit post-recovery ownership overrides, then build canonical candidate",
        },
        "absorbed_source_regions": absorbed,
        "remapped_decisions": remapped,
        "pending_or_keep_regions": [str(item["region"]) for item in unresolved],
    }
    (args.out / "reconciliation_decision_remap.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result["meta"], indent=2))


if __name__ == "__main__":
    main()
