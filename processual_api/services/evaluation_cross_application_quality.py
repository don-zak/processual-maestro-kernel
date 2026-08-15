"""Cross-application readiness evidence for External Evaluation campaigns.

Each external program is represented by its own campaign ``client_id``. Portability
is sufficient only when every supplied application campaign independently passes
endpoint quality and semantic task quality. This module never treats one client
as representative of another and does not fabricate external-run evidence.
"""

from __future__ import annotations

from typing import Any, Mapping

from processual_api.services.evaluation_quality_assessment import (
    assess_evaluation_campaign_quality,
)
from processual_api.services.evaluation_task_quality import (
    summarize_evaluation_task_quality,
)


def assess_cross_application_quality(
    raw: Mapping[str, Any],
    *,
    client_ids: tuple[str, ...],
    min_applications: int = 2,
    min_successes_per_endpoint: int = 3,
    min_outcome_passes: int = 3,
    max_failure_rate: float = 0.0,
    max_p95_latency_ms: float | None = None,
) -> dict[str, Any]:
    clients = tuple(dict.fromkeys(str(value or "").strip() for value in client_ids if str(value or "").strip()))
    if min_applications < 2 or min_applications > 10:
        raise ValueError("min_applications must be between 2 and 10")
    if len(clients) < min_applications:
        return {
            "required_application_count": min_applications,
            "observed_application_count": len(clients),
            "cross_application_quality_sufficient": False,
            "blocker_codes": ["multiple_external_application_campaigns_required"],
            "applications": [],
            "raw_secret_visible": False,
            "production_allowed": False,
        }

    applications: list[dict[str, Any]] = []
    for client_id in clients:
        endpoint_quality = assess_evaluation_campaign_quality(
            client_id=client_id,
            min_successes_per_endpoint=min_successes_per_endpoint,
            max_failure_rate=max_failure_rate,
            max_p95_latency_ms=max_p95_latency_ms,
        )
        task_quality = summarize_evaluation_task_quality(
            raw,
            client_id=client_id,
            min_outcome_passes=min_outcome_passes,
        )
        application_passed = (
            endpoint_quality["quality_gate_passed"] is True
            and task_quality["semantic_quality_sufficient"] is True
        )
        blockers: list[str] = []
        if endpoint_quality["quality_gate_passed"] is not True:
            blockers.append("endpoint_quality_incomplete")
        if task_quality["semantic_quality_sufficient"] is not True:
            blockers.append("semantic_task_quality_incomplete")
        applications.append(
            {
                "client_id": client_id,
                "endpoint_quality_passed": endpoint_quality["quality_gate_passed"],
                "semantic_task_quality_passed": task_quality["semantic_quality_sufficient"],
                "application_quality_passed": application_passed,
                "endpoint_quality_percent": endpoint_quality["quality_evidence_percent"],
                "task_binding_count": task_quality["task_binding_count"],
                "blocker_codes": blockers,
            }
        )

    passed_count = sum(1 for item in applications if item["application_quality_passed"])
    sufficient = passed_count >= min_applications and passed_count == len(applications)
    blockers = [] if sufficient else ["every_external_application_must_pass_independently"]
    return {
        "required_application_count": min_applications,
        "observed_application_count": len(applications),
        "passed_application_count": passed_count,
        "cross_application_quality_sufficient": sufficient,
        "blocker_codes": blockers,
        "thresholds": {
            "min_successes_per_endpoint": min_successes_per_endpoint,
            "min_outcome_passes": min_outcome_passes,
            "max_failure_rate": max_failure_rate,
            "max_p95_latency_ms": max_p95_latency_ms,
        },
        "applications": applications,
        "public_probe_evidence_required_per_application": True,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


__all__ = ["assess_cross_application_quality"]
