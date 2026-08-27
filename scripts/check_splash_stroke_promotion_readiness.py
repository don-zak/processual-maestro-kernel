#!/usr/bin/env python3
"""Fail-closed readiness gate for promoting canonical Splash stroke assets.

The live route SVGs must never be replaced from summaries, approximations, or
hand-authored geometry. Promotion is permitted only when the exact approved
reference image, the detailed canonical graph, and the detailed edge render
semantics are all present and independently agree with the promoted audit
contracts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from scripts.build_splash_runtime_manifest import compile_manifest

REFERENCE_SIZE = [1672, 941]
EXPECTED_CANONICAL_PIXELS = 18285
EXPECTED_ROUTE_TREES = 125
EXPECTED_EDGES = 5496
EXPECTED_COLOR_COUNTS = {"cyan": 3888, "teal": 81, "lime": 107, "violet": 501, "amber": 919}
EXPECTED_WIDTH_COUNTS = {"thin": 3002, "thick": 2494}
PROVENANCE_VERSION = "A3-splash-approved-reference-provenance-v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def load_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"Required promotion input is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"Expected JSON object: {path}")
    return payload


def png_size(path: Path) -> list[int]:
    require(path.is_file(), f"Approved reference image is missing: {path}")
    with path.open("rb") as handle:
        header = handle.read(24)
    require(header[:8] == b"\x89PNG\r\n\x1a\n", "Approved reference must be the reviewed PNG")
    width, height = struct.unpack(">II", header[16:24])
    return [width, height]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_reference(reference: Path, provenance: dict[str, object]) -> str:
    require(provenance.get("contract_version") == PROVENANCE_VERSION, "Untrusted approved-reference provenance contract")
    require(provenance.get("reviewed") is True, "Approved-reference provenance is not human-reviewed")
    require(provenance.get("source_of_truth") == "approved pivot reference image", "Reference provenance source-of-truth drift")
    require(provenance.get("reference_size") == REFERENCE_SIZE, "Reference provenance dimensions drift")
    require(png_size(reference) == REFERENCE_SIZE, "Approved reference PNG dimensions drift")
    expected_hash = str(provenance.get("sha256", "")).lower()
    require(len(expected_hash) == 64 and all(c in "0123456789abcdef" for c in expected_hash), "Approved reference SHA-256 is missing or invalid")
    actual_hash = sha256_file(reference)
    require(actual_hash == expected_hash, "Approved reference SHA-256 does not match reviewed provenance")
    return actual_hash


def validate_promoted_contracts(graph_audit: dict[str, object], render_contract: dict[str, object]) -> None:
    measured = graph_audit.get("measured_run", {})
    require(isinstance(measured, dict), "Canonical graph audit measured_run is missing")
    roundtrip = measured.get("graph_roundtrip", {})
    require(isinstance(roundtrip, dict), "Canonical graph roundtrip audit is missing")
    require(measured.get("canonical_pixel_count") == EXPECTED_CANONICAL_PIXELS, "Canonical pixel count drift")
    require(measured.get("route_tree_count") == EXPECTED_ROUTE_TREES, "Canonical route-tree count drift")
    require(roundtrip.get("roundtrip_exact") is True, "Canonical graph roundtrip is not exact")
    require(roundtrip.get("missing_pixel_count") == 0 and roundtrip.get("extra_pixel_count") == 0, "Canonical graph roundtrip contains pixel drift")
    require(graph_audit.get("canonical_geometry_ready") is True, "Canonical geometry audit is not promoted")

    geometry = render_contract.get("geometry", {})
    semantics = render_contract.get("render_semantics", {})
    final_review = render_contract.get("final_review", {})
    require(isinstance(geometry, dict) and isinstance(semantics, dict) and isinstance(final_review, dict), "Canonical render contract is incomplete")
    require(geometry.get("canonical_pixels") == EXPECTED_CANONICAL_PIXELS, "Render contract canonical pixel count drift")
    require(geometry.get("route_tree_count") == EXPECTED_ROUTE_TREES, "Render contract route-tree count drift")
    require(geometry.get("graph_roundtrip_exact") is True, "Render contract graph roundtrip is not exact")
    require(geometry.get("synthetic_geometry_pixels") == 0, "Synthetic canonical geometry is forbidden")
    require(semantics.get("edge_count") == EXPECTED_EDGES, "Render contract edge count drift")
    require(semantics.get("color_family_counts") == EXPECTED_COLOR_COUNTS, "Render contract color-family distribution drift")
    require(semantics.get("width_class_counts") == EXPECTED_WIDTH_COUNTS, "Render contract width-class distribution drift")
    require(semantics.get("zero_color_support_edge_count") == 0, "At least one canonical edge lacks reference color support")
    require(semantics.get("edge_color_assignment_complete") is True, "Canonical edge color assignment is incomplete")
    require(semantics.get("edge_width_assignment_complete") is True, "Canonical edge width assignment is incomplete")
    require(final_review.get("remaining_semantic_blockers") == 0, "Canonical render contract still has semantic blockers")
    require(final_review.get("canonical_render_manifest_ready") is True, "Canonical render manifest is not promoted")
    require(final_review.get("splash_reconstruction_allowed") is True, "Splash reconstruction is not authorized by the canonical contract")


def check_readiness(
    reference: Path,
    provenance_path: Path,
    graph_path: Path,
    semantics_path: Path,
    graph_audit_path: Path,
    render_contract_path: Path,
) -> dict[str, object]:
    provenance = load_json(provenance_path)
    graph = load_json(graph_path)
    semantics = load_json(semantics_path)
    graph_audit = load_json(graph_audit_path)
    render_contract = load_json(render_contract_path)

    reference_sha256 = validate_reference(reference, provenance)
    validate_promoted_contracts(graph_audit, render_contract)
    runtime = compile_manifest(graph, semantics)
    meta = runtime["meta"]
    require(meta["route_tree_count"] == EXPECTED_ROUTE_TREES, "Detailed graph route-tree count drift")
    require(meta["edge_count"] == EXPECTED_EDGES, "Detailed graph/semantics edge count drift")
    require(meta["color_family_counts"] == EXPECTED_COLOR_COUNTS, "Detailed render color distribution drift")
    require(meta["width_class_counts"] == EXPECTED_WIDTH_COUNTS, "Detailed render width distribution drift")
    require(meta["synthetic_geometry_pixels"] == 0, "Detailed runtime manifest contains synthetic geometry")

    return {
        "stroke_promotion_ready": True,
        "reference_sha256": reference_sha256,
        "reference_size": REFERENCE_SIZE,
        "canonical_pixels": EXPECTED_CANONICAL_PIXELS,
        "route_tree_count": EXPECTED_ROUTE_TREES,
        "edge_count": EXPECTED_EDGES,
        "color_family_counts": EXPECTED_COLOR_COUNTS,
        "width_class_counts": EXPECTED_WIDTH_COUNTS,
        "synthetic_geometry_pixels": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-provenance", type=Path, required=True)
    parser.add_argument("--canonical-graph", type=Path, required=True)
    parser.add_argument("--render-semantics", type=Path, required=True)
    parser.add_argument("--graph-audit", type=Path, required=True)
    parser.add_argument("--render-contract", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = check_readiness(
        args.reference,
        args.reference_provenance,
        args.canonical_graph,
        args.render_semantics,
        args.graph_audit,
        args.render_contract,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
