"""Aggregate task-level External Evaluation evidence without raw payloads."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from processual_api.services.evaluation_grants import evaluation_grants

_TASK_EVIDENCE_STORAGE_KEY = "evaluation_runtime_task_evidence_v1"


def summarize_evaluation_task_quality(
    raw: Mapping[str, Any],
    *,
    client_id: str,
    min_outcome_passes: int = 3,
) -> dict[str, Any]:
    client = str(client_id or "").strip()
    if not client:
        raise ValueError("client_id is required")
    if min_outcome_passes < 1 or min_outcome_passes > 100:
        raise ValueError("min_outcome_passes must be between 1 and 100")

    grant_ids = {
        str(grant.get("grant_id") or "")
        for grant in evaluation_grants(dict(raw))
        if str(grant.get("client_id") or "") == client
    }
    evidence = raw.get(_TASK_EVIDENCE_STORAGE_KEY, [])
    if not isinstance(evidence, list):
        evidence = []
    selected = [
        item
        for item in evidence
        if isinstance(item, dict)
        and str(item.get("evaluation_grant_id") or "") in grant_ids
    ]

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in selected:
        grouped[
            (
                str(item.get("task_id") or "unknown"),
                str(item.get("binding_id") or "unknown"),
            )
        ].append(item)

    rows: list[dict[str, Any]] = []
    for (task_id, binding_id), items in sorted(grouped.items()):
        completed_count = sum(1 for item in items if item.get("maestro_task_completed") is True)
        outcome_pass_count = sum(1 for item in items if item.get("outcome_validation_passed") is True)
        outcome_fail_count = sum(
            1
            for item in items
            if item.get("outcome_validation_status") == "failed"
        )
        outcome_missing_count = sum(
            1
            for item in items
            if item.get("outcome_validation_status") in {
                "missing_expectation",
                "task_incomplete",
                "unsupported_without_downstream_consumer",
                None,
            }
        )
        idempotency_required = any(item.get("idempotency_required") is True for item in items)
        idempotency_evidence_count = sum(
            1
            for item in items
            if item.get("idempotency_required") is True
            and bool(item.get("idempotency_reservation_id"))
        )
        semantic_pass = (
            outcome_pass_count >= min_outcome_passes
            and outcome_fail_count == 0
            and outcome_missing_count == 0
        )
        blockers: list[str] = []
        if completed_count == 0:
            blockers.append("completed_task_evidence_required")
        if outcome_pass_count < min_outcome_passes:
            blockers.append("repeatable_outcome_passes_required")
        if outcome_fail_count:
            blockers.append("semantic_outcome_failures_present")
        if outcome_missing_count:
            blockers.append("outcome_validation_missing_or_incomplete")
        if idempotency_required and idempotency_evidence_count != len(items):
            blockers.append("idempotency_evidence_incomplete")

        rows.append(
            {
                "task_id": task_id,
                "binding_id": binding_id,
                "attempt_count": len(items),
                "completed_count": completed_count,
                "outcome_pass_count": outcome_pass_count,
                "outcome_fail_count": outcome_fail_count,
                "outcome_missing_count": outcome_missing_count,
                "idempotency_required": idempotency_required,
                "idempotency_evidence_count": idempotency_evidence_count,
                "semantic_quality_sufficient": semantic_pass and not blockers,
                "blocker_codes": blockers,
            }
        )

    sufficient = bool(rows) and all(row["semantic_quality_sufficient"] for row in rows)
    return {
        "client_id": client,
        "grant_count": len(grant_ids),
        "task_binding_count": len(rows),
        "evidence_count": len(selected),
        "min_outcome_passes": min_outcome_passes,
        "semantic_quality_sufficient": sufficient,
        "tasks": rows,
        "raw_payload_visible": False,
        "raw_expected_values_visible": False,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


__all__ = ["summarize_evaluation_task_quality"]
