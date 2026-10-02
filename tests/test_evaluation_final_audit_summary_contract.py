from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_key_lifecycle.py"
UI = ROOT / "processual_api" / "static" / "js" / "admin_api_key_evaluation_lifecycle.js"
DELIVERY = ROOT / "processual_api" / "services" / "evaluation_runtime_delivery_postgres.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_final_audit_summary_requires_operator_qualification_decision() -> None:
    source = _source(ROUTER)

    assert '"report_type": "external_evaluation_final_summary"' in source
    assert '"audit_outcome": audit_outcome' in source
    assert '"qualification_decision": "operator_required"' in source
    assert 'audit_outcome = "complete"' in source
    assert 'audit_outcome = "needs_review"' in source
    assert 'audit_outcome = "not_evaluated"' in source
    assert '"verdict":' not in source


def test_final_summary_keeps_per_key_quota_distinct_from_aggregate_usage() -> None:
    source = _source(ROUTER)

    assert '"per_key_limit": per_key_limit' in source
    assert '"used_across_keys": quota_used' in source
    assert '"rejected_across_keys": quota_rejected' in source
    assert '"issued_key_count": len(keys)' in source
    assert '"semantics": "admitted_execution"' in source
    assert '"remaining": max(0, quota_limit - quota_used)' not in source


def test_admin_ui_renders_final_summary_without_automatic_qualification() -> None:
    source = _source(UI)

    assert "Final Evaluation Summary" in source
    assert "audit outcome" in source
    assert "qualification" in source
    assert "operator required" in source
    assert "per-key quota limit" in source
    assert "used across keys" in source
    assert "quota rejected across keys" in source
    assert "payload.summary || null" in source


def test_quota_rejection_is_raised_only_after_transaction_scope() -> None:
    source = _source(DELIVERY)

    transaction_start = source.index("async with session_scope() as session:", source.index("async def claim_evaluation_execution"))
    post_transaction_raise = source.index(
        'raise EvaluationQuotaExceededError("evaluation_execution_quota_exhausted")',
        transaction_start,
    )
    transaction_tail = source.index("except EvaluationDeliveryError:", transaction_start)

    assert "_record_quota_rejection(key)" in source[transaction_start:transaction_tail]
    assert post_transaction_raise > transaction_tail
    assert "Lock grant state before key" in source
