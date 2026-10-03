"""Qualification of the investor-facing internal synthetic evidence dossier."""
from __future__ import annotations

import asyncio
from pathlib import Path
import json
import hashlib

from ops.evaluation.capability_cases import build, CASES, NEGATIVE
from ops.evaluation.export_capability_dossier import write, MARKER, TEMPLATE


def test_capability_dossier_has_original_inputs_governance_and_all_seven_fate_components():
    report = asyncio.run(build())
    assert len(CASES) == 10
    assert len(NEGATIVE) == 6
    assert report["total"] == 16
    assert report["passed"] == 16
    assert report["workspace_evidence"] == "NOT_IMPORTED"
    assert report["real_external_calls"] == 0
    assert report["real_quota_consumed"] == 0
    assert sum(c["governance"]["disposition"] == "allow" for c in report["cases"]) == 7
    assert sum(c["governance"]["disposition"] == "allow_with_review" for c in report["cases"]) == 3
    assert sum(c["governance"]["disposition"] == "deny" for c in report["cases"]) == 6
    fields = {"stability", "hybridity", "distortion", "extinction",
              "collapse", "flourishing", "transient"}
    for case in report["cases"]:
        assert case["verification"]["passed"], case["case_id"]
        assert case["content"]["input"]
        assert case["governance"]["reason_codes"]
        assert set(case["governance"]["fate_vector"]) == fields
        assert set(case["governance"]["fate_signals"]) == {
            "compatibility", "coherence", "structural_support", "usefulness",
            "complexity", "fatigue", "shock", "lift", "novelty", "no_answer",
            "hallucination", "constraint_failure",
        }
        assert all(0 <= v <= 1 for v in case["governance"]["fate_vector"].values())
        assert all(case["verification"]["checks"].values())
        if case["governance"]["disposition"] == "deny":
            assert case["synthetic_kernel_receipt"] is None
        else:
            assert case["synthetic_kernel_receipt"]["maestro_task_completed"] is True
            assert case["synthetic_kernel_receipt"]["raw_secret_visible"] is False
            assert case["synthetic_kernel_receipt"]["production_allowed"] is False


def test_dossier_export_has_matching_hashes_no_live_claims(tmp_path: Path):
    report = asyncio.run(build())
    report["source_sha"] = "a" * 40
    report["limitations"] = ["Internal synthetic evidence only."]
    manifest = write(tmp_path, report)
    results = (tmp_path / "results.json").read_bytes()
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert hashlib.sha256(results).hexdigest() == manifest["results_sha256"]
    assert hashlib.sha256(html.encode()).hexdigest() == manifest["viewer_sha256"]
    assert json.loads(results)["source_sha"] == manifest["source_sha"]
    assert MARKER not in html
    assert "INTERNAL_SYNTHETIC" in html
    assert '"workspace_evidence":"NOT_IMPORTED"' in html
    assert manifest["workspace_execution_proved"] is False
    assert manifest["external_http_calls"] == 0


def test_viewer_has_accessible_bilingual_audit_detail_and_no_external_scripts():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert 'lang="en"' in html
    assert 'id="arabic"' in html
    assert 'id="english"' in html
    for required in ("fate_signals", "recomputed_vector", "synthetic_kernel_receipt",
                     "content.input", "reason_codes", "verification.checks", "trace_sha256"):
        assert required in html
    assert "replaceChildren()" in html
    assert "escape" not in html or "esc=" in html
    assert "https://cdn." not in html
    assert 'noindex,nofollow' in html
