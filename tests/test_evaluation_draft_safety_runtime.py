from __future__ import annotations

from pathlib import Path

from processual_api.routers import evaluation_runtime


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "processual_api" / "routers" / "evaluation_runtime.py"


def test_safe_replay_preserves_only_explicit_draft_safety_facts() -> None:
    response = {
        "status": "sandbox_proof_passed",
        "operation_class": "draft",
        "review_required": True,
        "applied": False,
        "production_mutation_performed": False,
        "production_allowed": False,
        "canonical_input": {"must": "not persist in replay"},
        "raw_provider_response": {"must": "not persist"},
        "raw_secret_visible": False,
    }

    safe = evaluation_runtime._safe_replay_response(response)

    assert safe["operation_class"] == "draft"
    assert safe["review_required"] is True
    assert safe["applied"] is False
    assert safe["production_mutation_performed"] is False
    assert safe["production_allowed"] is False
    assert safe["canonical_input_included"] is False
    assert safe["raw_response_included"] is False
    assert safe["raw_task_input_persisted"] is False
    assert safe["raw_secret_visible"] is False
    assert "canonical_input" not in safe
    assert "raw_provider_response" not in safe


def test_runtime_persists_draft_safety_facts_in_evidence_contract() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    evidence_block = source.split("    evidence = {", 1)[1].split("    response = {", 1)[0]

    assert '"review_required": result.get("review_required")' in evidence_block
    assert '"applied": result.get("applied")' in evidence_block
    assert (
        '"production_mutation_performed": '
        'result.get("production_mutation_performed")'
    ) in evidence_block
    assert '"production_allowed": False' in evidence_block
