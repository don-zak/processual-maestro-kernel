from processual_api.routers.settings_admin_evaluation_key_lifecycle import (
    _final_audit_summary,
)


def _grant() -> dict:
    return {
        "grant_id": "eval_qualification",
        "status": "revoked",
        "issued_to": "qualification.example",
        "client_id": "eval_client",
        "max_requests": 100,
        "allowed_task_ids": [
            "crm.customer_context",
            "crm.customer_state_summary",
        ],
        "allowed_binding_ids": ["evaluation.crm.customer_context.owned"],
    }


def test_final_audit_fails_closed_when_usage_has_no_receipt() -> None:
    summary = _final_audit_summary(
        grant=_grant(),
        keys=[
            {
                "key_id": "evalkey_qualification",
                "status": "revoked",
                "lifecycle_status": "revoked",
                "usage_count": 1,
                "quota_rejected_count": 0,
            }
        ],
        receipts=[],
    )

    assert summary["audit_outcome"] == "ledger_receipt_mismatch"
    assert summary["ledger_receipt_mismatch"] is True
    assert summary["qualification_decision"] == "operator_required"
    assert summary["grant_id"] == "eval_qualification"
    assert summary["grant_status"] == "revoked"
    assert summary["issued_to"] == "qualification.example"
    assert summary["client_id"] == "eval_client"
    assert summary["quota"]["used_across_keys"] == 1
    assert summary["executions"]["total"] == 0
    assert summary["tasks"] == [
        "crm.customer_context",
        "crm.customer_state_summary",
    ]
    assert summary["bindings"] == ["evaluation.crm.customer_context.owned"]
    assert summary["production_allowed"] is False
    assert summary["raw_task_input_persisted"] is False
    assert summary["raw_secret_visible"] is False


def test_final_audit_is_complete_with_persisted_success_receipt() -> None:
    summary = _final_audit_summary(
        grant=_grant(),
        keys=[
            {
                "key_id": "evalkey_qualification",
                "status": "revoked",
                "lifecycle_status": "revoked",
                "usage_count": 1,
                "quota_rejected_count": 0,
            }
        ],
        receipts=[
            {
                "execution_id": "exec_qualification",
                "status": "succeeded",
                "task_id": "crm.customer_context",
                "binding_id": "evaluation.crm.customer_context.owned",
                "evidence_persisted_at": "2026-09-12T09:14:27+00:00",
            }
        ],
    )

    assert summary["audit_outcome"] == "complete"
    assert summary["ledger_receipt_mismatch"] is False
    assert summary["quota"]["used_across_keys"] == 1
    assert summary["executions"]["total"] == 1
    assert summary["executions"]["succeeded"] == 1
    assert summary["executions"]["evidence_persisted"] == 1
    assert summary["tasks"] == [
        "crm.customer_context",
        "crm.customer_state_summary",
    ]
    assert summary["bindings"] == ["evaluation.crm.customer_context.owned"]
