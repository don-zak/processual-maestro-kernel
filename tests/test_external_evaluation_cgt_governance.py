from __future__ import annotations

from pathlib import Path

from processual_api.services.evaluation_cgt_governance import (
    EVALUATION_CGT_POLICY_VERSION,
    evaluate_evaluation_cgt_governance,
    governed_execution_evidence_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
ROUTE_REGISTRY = ROOT / "processual_api" / "routers" / "external_evaluation_route_registry.py"


def _decision(operation_class: str, **overrides):
    payload = {
        "grant_id": "eval_test",
        "api_key_id": "evalkey_test",
        "task_id": "crm.customer_context",
        "binding_id": "evaluation.crm.customer_context.owned",
        "operation_class": operation_class,
        "task_input": {"customer_id": 1},
        "sandbox_allowed": True,
        "auto_execute_production": False,
        "production_allowed": False,
    }
    payload.update(overrides)
    return evaluate_evaluation_cgt_governance(**payload)


def test_cgt_allows_bounded_read_without_expanding_grant() -> None:
    result = _decision("read")
    assert result["disposition"] == "allow"
    assert result["governance_action"] == "keep"
    assert result["policy_version"] == EVALUATION_CGT_POLICY_VERSION
    assert result["authority_expansion_allowed"] is False
    assert result["production_allowed"] is False
    assert result["raw_task_input_included"] is False
    assert len(result["trace_sha256"]) == 64


def test_cgt_requires_supervisor_review_for_draft() -> None:
    result = _decision(
        "draft",
        task_id="crm.customer_update_draft",
        binding_id="evaluation.crm.customer_update_draft.owned",
    )
    assert result["disposition"] == "allow_with_review"
    assert result["governance_action"] == "repair"
    assert result["review_required"] is True
    assert "supervisor_review_required" in result["reason_codes"]
    assert "production_mutation_forbidden" in result["reason_codes"]


def test_cgt_denies_non_sandbox_or_production_authority() -> None:
    result = _decision("read", sandbox_allowed=False)
    assert result["disposition"] == "deny"
    assert result["governance_action"] == "reject"
    assert "external_evaluation_sandbox_only" in result["reason_codes"]

    production = _decision("read", production_allowed=True)
    assert production["disposition"] == "deny"
    assert production["production_allowed"] is False


def test_governance_trace_is_deterministic_and_input_is_hashed_only() -> None:
    first = _decision("read")
    second = _decision("read")
    assert first["decision_id"] == second["decision_id"]
    assert first["trace_sha256"] == second["trace_sha256"]
    assert first["task_input_sha256"] == second["task_input_sha256"]
    assert "customer_id" not in repr(first)


def test_combined_digest_binds_governance_and_execution_evidence() -> None:
    digest = governed_execution_evidence_sha256(
        execution_evidence_sha256="a" * 64,
        governance_trace_sha256="b" * 64,
    )
    assert len(digest) == 64
    assert digest != "a" * 64
    assert digest != "b" * 64


def test_external_evaluation_routes_use_cgt_governed_runtime() -> None:
    source = ROUTE_REGISTRY.read_text(encoding="utf-8")
    assert "governed_execute_evaluation_runtime_task" in source
    assert "evaluation_runtime_status_with_governance" in source
    assert '"/evaluation/runtime/task-execute"' in source
    assert '"/evaluation/runtime/status"' in source
