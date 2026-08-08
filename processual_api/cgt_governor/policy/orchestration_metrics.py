"""Low-cardinality metrics for real LLM orchestration fan-out."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from prometheus_client import Counter, Histogram

    ORCHESTRATION_REQUESTS = Counter(
        "maestro_llm_orchestration_requests_total",
        "LLM orchestration requests by planner decision and terminal outcome.",
        ["paced", "plan_reason", "outcome"],
    )
    ORCHESTRATION_WIDTH = Histogram(
        "maestro_llm_orchestration_width",
        "Prompt fan-out width observed by the LLM orchestration API.",
        ["paced", "plan_reason"],
        buckets=(1, 2, 4, 8, 12, 16, 24, 32),
    )
    ORCHESTRATION_LATENCY = Histogram(
        "maestro_llm_orchestration_latency_seconds",
        "End-to-end latency for LLM orchestration requests.",
        ["paced", "plan_reason", "outcome"],
        buckets=(0.1, 0.25, 0.5, 1, 2, 4, 8, 16, 32),
    )
    ORCHESTRATION_ITEM_OUTCOMES = Counter(
        "maestro_llm_orchestration_item_outcomes_total",
        "Per-item outcomes produced by the LLM orchestration API.",
        ["paced", "plan_reason", "outcome"],
    )
    _PROMETHEUS_AVAILABLE = True
except Exception:
    _PROMETHEUS_AVAILABLE = False


_ALLOWED_REASONS = {"broad_single_provider", "shared_governor_only"}
_ALLOWED_OUTCOMES = {"success", "partial_error", "saturated"}


@dataclass(frozen=True, slots=True)
class OrchestrationObservation:
    paced: bool
    plan_reason: str
    width: int
    outcome: str
    latency_seconds: float
    success_items: int
    error_items: int


def record_orchestration(observation: OrchestrationObservation) -> None:
    """Record one completed orchestration without high-cardinality labels."""

    if not _PROMETHEUS_AVAILABLE:
        return

    paced = "true" if observation.paced else "false"
    reason = _bounded_reason(observation.plan_reason)
    outcome = _bounded_outcome(observation.outcome)
    latency = max(observation.latency_seconds, 0.0)
    width = max(observation.width, 0)

    ORCHESTRATION_REQUESTS.labels(
        paced=paced,
        plan_reason=reason,
        outcome=outcome,
    ).inc()
    ORCHESTRATION_WIDTH.labels(
        paced=paced,
        plan_reason=reason,
    ).observe(width)
    ORCHESTRATION_LATENCY.labels(
        paced=paced,
        plan_reason=reason,
        outcome=outcome,
    ).observe(latency)

    if observation.success_items:
        ORCHESTRATION_ITEM_OUTCOMES.labels(
            paced=paced,
            plan_reason=reason,
            outcome="success",
        ).inc(observation.success_items)
    if observation.error_items:
        ORCHESTRATION_ITEM_OUTCOMES.labels(
            paced=paced,
            plan_reason=reason,
            outcome="error",
        ).inc(observation.error_items)


def _bounded_reason(reason: str) -> str:
    return reason if reason in _ALLOWED_REASONS else "unknown"


def _bounded_outcome(outcome: str) -> str:
    return outcome if outcome in _ALLOWED_OUTCOMES else "unknown"
