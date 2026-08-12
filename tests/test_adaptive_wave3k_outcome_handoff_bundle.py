from __future__ import annotations

import pytest

from processual_kernel.adaptive.handoff_advisor import HandoffSchemaAdvisor
from processual_kernel.adaptive.outcome_evaluator import OutcomeEvaluator, _clamp
from processual_kernel.types import HandoffTelemetry


def _valid_payload() -> dict[str, object]:
    return {
        "objective": "handoff objective",
        "inputs_used": ["artifact-a", "artifact-b"],
        "key_findings": ["finding"],
        "assumptions": ["assumption"],
        "open_questions": [],
        "validation_status": "checked",
        "next_agent_action": "continue",
    }


def test_handoff_advisor_marks_weak_edges_for_mediation() -> None:
    advisor = HandoffSchemaAdvisor()

    by_negative_psi = advisor.advise("a->b", edge_psi=-0.01)
    by_ambiguity = advisor.advise("b->c", HandoffTelemetry(ambiguity=0.65, rework_rate=0.0), edge_psi=0.2)
    by_rework = advisor.advise("c->d", HandoffTelemetry(ambiguity=0.0, rework_rate=0.50), edge_psi=0.2)

    for suggestion in (by_negative_psi, by_ambiguity, by_rework):
        assert suggestion.recommend_mediator is True
        assert suggestion.confidence == 0.82
        assert suggestion.reason == "handoff quality is weak or ambiguous"
        assert suggestion.summary_format == "objective -> evidence -> risks -> next_action"
        assert "validation_status" in suggestion.required_fields
        assert len(suggestion.validation_rules) == 5
        assert len(suggestion.checklist) == 4


def test_handoff_advisor_returns_consistency_schema_for_healthy_edge() -> None:
    suggestion = HandoffSchemaAdvisor().advise(
        "healthy",
        HandoffTelemetry(ambiguity=0.2, rework_rate=0.1),
        edge_psi=0.1,
    )

    assert suggestion.recommend_mediator is False
    assert suggestion.confidence == 0.62
    assert suggestion.reason == "schema can improve consistency"
    assert suggestion.required_fields == (
        "objective",
        "inputs_used",
        "key_findings",
        "assumptions",
        "open_questions",
        "validation_status",
        "next_agent_action",
    )


def test_handoff_advisor_defaults_without_telemetry_are_weak() -> None:
    suggestion = HandoffSchemaAdvisor().advise("default")

    assert suggestion.recommend_mediator is True
    assert suggestion.confidence == 0.82


def test_handoff_payload_validation_accepts_complete_payload() -> None:
    advisor = HandoffSchemaAdvisor()
    suggestion = advisor.advise("a->b", HandoffTelemetry(ambiguity=0.1, rework_rate=0.1), edge_psi=0.2)

    result = advisor.validate_payload(_valid_payload(), suggestion)

    assert result.edge_id == "a->b"
    assert result.valid is True
    assert result.missing_fields == ()
    assert result.failed_rules == ()
    assert result.confidence == 1.0


@pytest.mark.parametrize("missing_value", [None, ""])
def test_handoff_payload_validation_reports_missing_scalar_fields(missing_value: object) -> None:
    advisor = HandoffSchemaAdvisor()
    suggestion = advisor.advise("a->b")
    payload = _valid_payload()
    payload["objective"] = missing_value

    result = advisor.validate_payload(payload, suggestion)

    assert result.valid is False
    assert result.missing_fields == ("objective",)
    assert result.failed_rules == ()
    assert result.confidence == 0.88


def test_handoff_payload_validation_treats_empty_required_lists_as_missing_except_open_questions() -> None:
    advisor = HandoffSchemaAdvisor()
    suggestion = advisor.advise("a->b")
    payload = _valid_payload()
    payload["inputs_used"] = []

    result = advisor.validate_payload(payload, suggestion)

    assert result.valid is False
    assert result.missing_fields == ("inputs_used",)
    assert result.failed_rules == ()
    assert result.confidence == 0.88


def test_handoff_payload_validation_reports_invalid_status_and_collection_types() -> None:
    advisor = HandoffSchemaAdvisor()
    suggestion = advisor.advise("a->b")
    payload = _valid_payload()
    payload["validation_status"] = "unknown"
    payload["inputs_used"] = "artifact-a"
    payload["open_questions"] = "none"

    result = advisor.validate_payload(payload, suggestion)

    assert result.valid is False
    assert result.missing_fields == ()
    assert result.failed_rules == (
        "validation_status must be one of: draft, checked, blocked",
        "inputs_used must list upstream artifacts",
        "open_questions must be a list, even when empty",
    )
    assert result.confidence == 0.64


def test_handoff_payload_validation_confidence_is_clamped_at_zero() -> None:
    advisor = HandoffSchemaAdvisor()
    suggestion = advisor.advise("a->b")

    result = advisor.validate_payload({}, suggestion)

    assert result.valid is False
    assert set(result.missing_fields) == set(suggestion.required_fields)
    assert result.failed_rules == ("validation_status must be one of: draft, checked, blocked",)
    assert result.confidence == 0.04


def test_clamp_respects_default_and_custom_bounds() -> None:
    assert _clamp(-3.0) == 0.0
    assert _clamp(0.4) == 0.4
    assert _clamp(3.0) == 1.0
    assert _clamp(5.0, 2.0, 4.0) == 4.0
    assert _clamp(1.0, 2.0, 4.0) == 2.0


def test_outcome_evaluator_scores_successful_improvement_and_persists_result() -> None:
    evaluator = OutcomeEvaluator()

    outcome = evaluator.evaluate(
        decision_id="d-success",
        action="reroute",
        expected_effect="improve",
        actual_result="SUCCESS",
        quality_delta=0.4,
        cost_delta=-0.2,
        latency_delta=-0.1,
        recovery_time_delta=-0.2,
        success_probability_delta=0.3,
    )

    assert outcome.decision_quality == 0.935
    assert outcome.action == "reroute"
    assert outcome.expected_effect == "improve"
    assert evaluator.outcomes == {"d-success": outcome}


def test_outcome_evaluator_penalizes_unsuccessful_regression_and_clamps_low() -> None:
    evaluator = OutcomeEvaluator()

    outcome = evaluator.evaluate(
        decision_id="d-fail",
        action="retry",
        expected_effect="recover",
        actual_result="failed",
        quality_delta=-2.0,
        cost_delta=2.0,
        latency_delta=2.0,
        recovery_time_delta=2.0,
        success_probability_delta=-2.0,
    )

    assert outcome.decision_quality == 0.0
    assert evaluator.outcomes["d-fail"] is outcome


@pytest.mark.parametrize("actual_result", ["success", "improved", "recovered"])
def test_outcome_evaluator_success_bias_applies_to_all_supported_results(actual_result: str) -> None:
    score = OutcomeEvaluator._score(actual_result, 0.0, 0.0, 0.0, 0.0, 0.0, None)

    assert score == 0.7


def test_outcome_evaluator_non_success_result_uses_negative_bias() -> None:
    score = OutcomeEvaluator._score("unchanged", 0.0, 0.0, 0.0, 0.0, 0.0, None)

    assert score == 0.35


def test_outcome_evaluator_human_feedback_is_clamped_and_blended() -> None:
    high = OutcomeEvaluator._score("success", 0.0, 0.0, 0.0, 0.0, 0.0, 5.0)
    low = OutcomeEvaluator._score("success", 0.0, 0.0, 0.0, 0.0, 0.0, -5.0)
    mid = OutcomeEvaluator._score("success", 0.0, 0.0, 0.0, 0.0, 0.0, 0.4)

    assert high == 0.775
    assert low == 0.525
    assert mid == 0.625


def test_outcome_evaluator_clamps_extreme_positive_score() -> None:
    score = OutcomeEvaluator._score(
        "improved",
        quality_delta=3.0,
        cost_delta=-3.0,
        latency_delta=-3.0,
        recovery_time_delta=-3.0,
        success_probability_delta=3.0,
        human_feedback_score=None,
    )

    assert score == 1.0


def test_outcome_evaluator_replaces_existing_decision_id() -> None:
    evaluator = OutcomeEvaluator()
    first = evaluator.evaluate("same", "observe", "check", "unchanged")
    second = evaluator.evaluate("same", "reroute", "improve", "recovered")

    assert first.decision_quality == 0.35
    assert second.decision_quality == 0.7
    assert evaluator.outcomes == {"same": second}
