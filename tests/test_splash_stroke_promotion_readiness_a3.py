from __future__ import annotations

import copy
import hashlib
import json
import struct
from pathlib import Path

import pytest

from scripts.check_splash_stroke_promotion_readiness import (
    PROVENANCE_VERSION,
    REFERENCE_SIZE,
    check_readiness,
    validate_promoted_contracts,
    validate_reference,
)

ROOT = Path(__file__).resolve().parents[1]
GRAPH_AUDIT = ROOT / "tests/fixtures/splash_reference_canonical_graph_audit_a3.json"
RENDER_CONTRACT = ROOT / "tests/fixtures/splash_reference_canonical_render_manifest_a3.json"


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_reference_header(path: Path, width: int = 1672, height: int = 941) -> str:
    # The readiness helper intentionally validates only immutable identity evidence
    # here (PNG signature, dimensions, SHA-256). Image-content semantics remain the
    # responsibility of the recovered, reviewed production reference and its hash.
    payload = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", width, height)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def provenance(reference_sha256: str, *, reviewed: bool = True) -> dict[str, object]:
    return {
        "contract_version": PROVENANCE_VERSION,
        "reviewed": reviewed,
        "source_of_truth": "approved pivot reference image",
        "reference_size": REFERENCE_SIZE,
        "sha256": reference_sha256,
    }


def test_promoted_contracts_match_locked_canonical_evidence() -> None:
    validate_promoted_contracts(load_json(GRAPH_AUDIT), load_json(RENDER_CONTRACT))


def test_promoted_contracts_reject_synthetic_geometry() -> None:
    graph_audit = load_json(GRAPH_AUDIT)
    render_contract = copy.deepcopy(load_json(RENDER_CONTRACT))
    render_contract["geometry"]["synthetic_geometry_pixels"] = 1

    with pytest.raises(SystemExit, match="Synthetic canonical geometry is forbidden"):
        validate_promoted_contracts(graph_audit, render_contract)


def test_promoted_contracts_reject_distribution_drift_with_same_total() -> None:
    graph_audit = load_json(GRAPH_AUDIT)
    render_contract = copy.deepcopy(load_json(RENDER_CONTRACT))
    counts = render_contract["render_semantics"]["color_family_counts"]
    counts["cyan"] -= 1
    counts["amber"] += 1

    with pytest.raises(SystemExit, match="color-family distribution drift"):
        validate_promoted_contracts(graph_audit, render_contract)


def test_reference_requires_reviewed_hash_bound_provenance(tmp_path: Path) -> None:
    reference = tmp_path / "approved.png"
    digest = write_reference_header(reference)

    assert validate_reference(reference, provenance(digest)) == digest

    with pytest.raises(SystemExit, match="not human-reviewed"):
        validate_reference(reference, provenance(digest, reviewed=False))

    bad_hash = "0" * 64 if digest != "0" * 64 else "1" * 64
    with pytest.raises(SystemExit, match="SHA-256 does not match"):
        validate_reference(reference, provenance(bad_hash))


def test_reference_rejects_dimension_drift_even_with_matching_hash(tmp_path: Path) -> None:
    reference = tmp_path / "wrong-size.png"
    digest = write_reference_header(reference, width=1671)

    with pytest.raises(SystemExit, match="PNG dimensions drift"):
        validate_reference(reference, provenance(digest))


def test_readiness_fails_closed_without_detailed_graph_and_semantics(tmp_path: Path) -> None:
    reference = tmp_path / "approved.png"
    digest = write_reference_header(reference)
    provenance_path = tmp_path / "reference-provenance.json"
    provenance_path.write_text(json.dumps(provenance(digest)), encoding="utf-8")

    with pytest.raises(SystemExit, match="Required promotion input is missing"):
        check_readiness(
            reference,
            provenance_path,
            tmp_path / "canonical_graph_candidate.json",
            tmp_path / "reference_render_semantics_audit.json",
            GRAPH_AUDIT,
            RENDER_CONTRACT,
        )
