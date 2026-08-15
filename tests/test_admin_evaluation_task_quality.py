from __future__ import annotations

from processual_api.services.evaluation_grants import EVALUATION_GRANTS_STORAGE_KEY
from processual_api.services.evaluation_task_quality import (
    summarize_evaluation_task_quality,
)


def _raw_with_evidence(*, statuses: list[str]) -> dict:
    evidence = []
    for index, status in enumerate(statuses):
        passed = status == "passed"
        evidence.append(
            {
                "execution_id": f"exec-{index}",
                "evaluation_grant_id": "eval-read",
                "api_key_id": "evalkey-read",
                "binding_id": "binding-crm-read",
                "task_id": "crm.customer_context",
                "operation_class": "read",
                "maestro_task_completed": True,
                "outcome_validation_status": status,
                "outcome_validation_passed": passed,
                "outcome_validation_sha256": f"hash-{index}" if status != "missing_expectation" else None,
                "idempotency_required": False,
            }
        )
    return {
        EVALUATION_GRANTS_STORAGE_KEY: [
            {"grant_id": "eval-read", "client_id": "external-app-a"},
            {"grant_id": "eval-other", "client_id": "external-app-b"},
        ],
        "evaluation_runtime_task_evidence_v1": evidence,
    }


def test_task_quality_requires_repeatable_semantic_passes() -> None:
    raw = _raw_with_evidence(statuses=["passed", "passed"])
    summary = summarize_evaluation_task_quality(
        raw,
        client_id="external-app-a",
        min_outcome_passes=3,
    )

    assert summary["semantic_quality_sufficient"] is False
    row = summary["tasks"][0]
    assert row["outcome_pass_count"] == 2
    assert "repeatable_outcome_passes_required" in row["blocker_codes"]


def test_task_quality_passes_after_three_clean_semantic_results() -> None:
    raw = _raw_with_evidence(statuses=["passed", "passed", "passed"])
    summary = summarize_evaluation_task_quality(
        raw,
        client_id="external-app-a",
        min_outcome_passes=3,
    )

    assert summary["semantic_quality_sufficient"] is True
    row = summary["tasks"][0]
    assert row["attempt_count"] == 3
    assert row["completed_count"] == 3
    assert row["outcome_pass_count"] == 3
    assert row["blocker_codes"] == []


def test_semantic_failure_blocks_quality_even_with_three_passes() -> None:
    raw = _raw_with_evidence(statuses=["passed", "passed", "passed", "failed"])
    summary = summarize_evaluation_task_quality(
        raw,
        client_id="external-app-a",
        min_outcome_passes=3,
    )

    assert summary["semantic_quality_sufficient"] is False
    row = summary["tasks"][0]
    assert row["outcome_fail_count"] == 1
    assert "semantic_outcome_failures_present" in row["blocker_codes"]


def test_missing_expectation_blocks_semantic_quality() -> None:
    raw = _raw_with_evidence(statuses=["passed", "passed", "passed", "missing_expectation"])
    summary = summarize_evaluation_task_quality(
        raw,
        client_id="external-app-a",
        min_outcome_passes=3,
    )

    assert summary["semantic_quality_sufficient"] is False
    row = summary["tasks"][0]
    assert row["outcome_missing_count"] == 1
    assert "outcome_validation_missing_or_incomplete" in row["blocker_codes"]


def test_task_quality_filters_evidence_by_campaign_client_id() -> None:
    raw = _raw_with_evidence(statuses=["passed", "passed", "passed"])
    raw["evaluation_runtime_task_evidence_v1"].append(
        {
            "evaluation_grant_id": "eval-other",
            "binding_id": "binding-other",
            "task_id": "billing.account_context",
            "maestro_task_completed": True,
            "outcome_validation_status": "failed",
            "outcome_validation_passed": False,
        }
    )

    summary = summarize_evaluation_task_quality(
        raw,
        client_id="external-app-a",
        min_outcome_passes=3,
    )

    assert summary["semantic_quality_sufficient"] is True
    assert summary["task_binding_count"] == 1
    assert summary["tasks"][0]["task_id"] == "crm.customer_context"
