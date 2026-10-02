from __future__ import annotations

from pathlib import Path

from processual_api.services.evaluation_cgt_denial_postgres import _safe_governance

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "processual_api" / "routers" / "evaluation_cgt_runtime.py"
DENIAL = ROOT / "processual_api" / "services" / "evaluation_cgt_denial_postgres.py"
DELIVERY = ROOT / "processual_api" / "services" / "evaluation_runtime_delivery_postgres.py"


def test_denial_evidence_contract_is_zero_quota_and_no_network() -> None:
    source = DENIAL.read_text(encoding="utf-8")
    assert '"quota_consumed": False' in source
    assert '"network_request_executed": False' in source
    assert '"evaluation_stage": "cgt_governance_denied_before_admission"' in source
    assert 'failure_code="CGTGovernanceDenied"' in source
    assert 'network_outcome="not_executed"' in source
    assert "_consume_admission_quota" not in source


def test_runtime_persists_deny_before_returning_403() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    persist_index = source.index("await persist_evaluation_cgt_denial(")
    raise_index = source.index("raise HTTPException(", persist_index)
    execute_index = source.index("response = await execute_evaluation_runtime_task")
    assert persist_index < raise_index < execute_index
    assert '"quota_consumed": False' in source
    assert '"network_request_executed": False' in source
    assert '"authority_expansion_allowed": False' in source


def test_governance_safe_projection_excludes_raw_material() -> None:
    projected = _safe_governance(
        {
            "decision_id": "cgt_eval_test",
            "policy_version": "external-evaluation-cgt-v1",
            "disposition": "deny",
            "task_input_sha256": "a" * 64,
            "raw_task_input": {"secret": "do-not-store"},
            "provider_secret": "do-not-store",
            "production_allowed": True,
            "authority_expansion_allowed": True,
        }
    )
    assert projected["decision_id"] == "cgt_eval_test"
    assert projected["production_allowed"] is False
    assert projected["authority_expansion_allowed"] is False
    assert "raw_task_input" not in projected
    assert "provider_secret" not in projected


def test_admin_audit_allowlist_carries_safe_governance_proof() -> None:
    source = DELIVERY.read_text(encoding="utf-8")
    for marker in (
        '"governance"',
        '"governance_decision_id"',
        '"governance_policy_version"',
        '"governance_disposition"',
        '"governance_trace_sha256"',
        '"governed_execution_evidence_sha256"',
        '"governance_enforced_before_admission"',
    ):
        assert marker in source
    assert 'governance_safe["raw_task_input_included"] = False' in source
    assert 'governance_safe["raw_secret_visible"] = False' in source
