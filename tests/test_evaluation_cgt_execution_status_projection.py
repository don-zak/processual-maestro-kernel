from __future__ import annotations

from processual_api.routers.evaluation_cgt_runtime import (
    _project_committed_governance_into_execution_status,
)


def test_committed_cgt_projection_removes_stale_null_governance_status() -> None:
    original = {
        "execution_id": "exec_projection",
        "record_id": "record_projection",
        "status": "succeeded",
        "governance_decision_id": None,
        "governance_policy_version": None,
        "governance_disposition": None,
        "governance_trace_sha256": None,
        "governed_execution_evidence_sha256": None,
        "governance_enforced_before_admission": False,
        "governance": None,
        "production_allowed": False,
    }
    governance = {
        "decision_id": "cgt_eval_projection",
        "policy_version": "external-evaluation-cgt-v1",
        "disposition": "allow_with_review",
        "trace_sha256": "b" * 64,
        "review_required": True,
        "production_allowed": False,
        "authority_expansion_allowed": False,
    }

    projected = _project_committed_governance_into_execution_status(
        original,
        governance=governance,
        governed_execution_evidence_sha256="c" * 64,
    )

    assert projected["execution_id"] == "exec_projection"
    assert projected["governance_decision_id"] == "cgt_eval_projection"
    assert projected["governance_policy_version"] == "external-evaluation-cgt-v1"
    assert projected["governance_disposition"] == "allow_with_review"
    assert projected["governance_trace_sha256"] == "b" * 64
    assert projected["governed_execution_evidence_sha256"] == "c" * 64
    assert projected["governance_enforced_before_admission"] is True
    assert projected["governance"] == governance
    assert original["governance_decision_id"] is None
    assert original["governance_enforced_before_admission"] is False
