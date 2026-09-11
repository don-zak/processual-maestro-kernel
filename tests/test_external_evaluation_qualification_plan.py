from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "EXTERNAL_EVALUATION_OPERATIONAL_RUNBOOK.md"
POSTGRES_INTEGRATION = (
    ROOT / "tests" / "integration" / "test_evaluation_runtime_delivery_postgres_integration.py"
)
QUOTA_POLICY = ROOT / "processual_api" / "services" / "evaluation_key_quota_policy.py"
AUTHORITY = ROOT / "processual_api" / "services" / "evaluation_authority_postgres.py"
FINAL_AUDIT = (
    ROOT / "processual_api" / "routers" / "settings_admin_evaluation_key_lifecycle.py"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_live_qualification_matrix_is_bounded_and_complete() -> None:
    runbook = _read(RUNBOOK)

    for stage in (
        "Q1 — Exact-head runtime and owned-sandbox readiness",
        "Q2 — Owned CRM preset, Grant authority and key handoff",
        "Q3 — Customer status/dashboard",
        "Q4 — New admitted execution",
        "Q5 — Durable replay",
        "Q6 — Idempotency conflict",
        "Q7 — Individual key revocation",
        "Q8 — Grant revocation",
        "Q9 — Final audit",
        "Q10 — Quota exhaustion and concurrency safety",
    ):
        assert stage in runbook

    for contract in (
        "CRM `100`, Integration `200`",
        "consumes exactly **1** unit",
        "consumes **0 additional** units",
        "expect HTTP `409`",
        "external_evaluation_final_summary",
        "qualification_decision=operator_required",
    ):
        assert contract in runbook


def test_owned_preset_live_plan_is_fail_closed_and_does_not_create_authority() -> None:
    runbook = _read(RUNBOOK)

    for contract in (
        "Prepare & prove CRM-CONTEXT-01",
        "selectable=true",
        "project-owned synthetic content",
        "project-scoped `anonymous/public` credential reference",
        "The preset itself must not create an Evaluation Grant or API key.",
        "The preset prepares/proves a binding only and cannot create or widen Grant authority.",
        "0/100` to `1/100 used",
        "remaining from `100` to `99`",
    ):
        assert contract in runbook


def test_live_plan_forbids_quota_exhaustion_burn() -> None:
    runbook = _read(RUNBOOK)

    assert "Integration-test database only; do not burn a live customer/evaluator quota to exhaustion." in runbook
    assert "must not consume 100/200 executions merely to demonstrate `429`" in runbook
    assert "Q1 through Q9 have the required live proof, using only bounded synthetic executions" in runbook


def test_destructive_quota_proof_is_backed_by_postgres_integration_test() -> None:
    integration = _read(POSTGRES_INTEGRATION)

    assert "test_same_key_race_claims_once_then_replays_and_consumes_one_unit" in integration
    assert "asyncio.gather(claim(), claim())" in integration
    assert 'assert replay["status"] == "replay"' in integration
    assert "assert authority_key.usage_count == 1" in integration
    assert "with pytest.raises(delivery.EvaluationQuotaExceededError)" in integration
    assert "with pytest.raises(delivery.EvaluationIdempotencyConflictError)" in integration
    assert "assert authority_key.quota_rejected_count == 1" in integration


def test_runtime_status_keeps_grant_type_authoritative() -> None:
    authority = _read(AUTHORITY)

    grant_first = 'grant.get("evaluation_type") or payload.get("evaluation_type")'
    payload_first = 'payload.get("evaluation_type") or grant.get("evaluation_type")'
    assert grant_first in authority
    assert payload_first not in authority


def test_qualification_plan_matches_authoritative_quota_and_final_audit_code() -> None:
    quota = _read(QUOTA_POLICY)
    audit = _read(FINAL_AUDIT)

    assert "CRM_EVALUATION_KEY_QUOTA = 100" in quota
    assert "INTEGRATION_EVALUATION_KEY_QUOTA_MULTIPLIER = 2" in quota
    assert '"report_type": "external_evaluation_final_summary"' in audit
    assert '"qualification_decision": "operator_required"' in audit
    assert '"verdict":' not in audit
