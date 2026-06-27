from __future__ import annotations

from ..adaptive_types import DecisionOutcome


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


class OutcomeEvaluator:
    """Scores whether a governance decision actually improved the workflow."""

    def __init__(self):
        self.outcomes: dict[str, DecisionOutcome] = {}

    def evaluate(
        self,
        decision_id: str,
        action: str,
        expected_effect: str,
        actual_result: str,
        quality_delta: float = 0.0,
        cost_delta: float = 0.0,
        latency_delta: float = 0.0,
        recovery_time_delta: float = 0.0,
        success_probability_delta: float = 0.0,
        human_feedback_score: float | None = None,
    ) -> DecisionOutcome:
        decision_quality = self._score(
            actual_result,
            quality_delta,
            cost_delta,
            latency_delta,
            recovery_time_delta,
            success_probability_delta,
            human_feedback_score,
        )
        outcome = DecisionOutcome(
            decision_id=decision_id,
            action=action,
            expected_effect=expected_effect,
            actual_result=actual_result,
            quality_delta=quality_delta,
            cost_delta=cost_delta,
            latency_delta=latency_delta,
            recovery_time_delta=recovery_time_delta,
            success_probability_delta=success_probability_delta,
            human_feedback_score=human_feedback_score,
            decision_quality=decision_quality,
        )
        self.outcomes[decision_id] = outcome
        return outcome

    @staticmethod
    def _score(
        actual_result: str,
        quality_delta: float,
        cost_delta: float,
        latency_delta: float,
        recovery_time_delta: float,
        success_probability_delta: float,
        human_feedback_score: float | None,
    ) -> float:
        success_bias = 0.20 if actual_result.lower() in {"success", "improved", "recovered"} else -0.15
        # Positive quality/success deltas help. Negative cost/latency/recovery deltas help.
        raw = 0.50
        raw += success_bias
        raw += 0.25 * quality_delta
        raw += 0.20 * success_probability_delta
        raw += 0.15 * (-cost_delta)
        raw += 0.15 * (-latency_delta)
        raw += 0.15 * (-recovery_time_delta)
        if human_feedback_score is not None:
            raw = 0.75 * raw + 0.25 * _clamp(human_feedback_score)
        return round(_clamp(raw), 4)
