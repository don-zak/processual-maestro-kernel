from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import pytest

from processual_api.cgt_governor.governor import (
    SanitizedGovernedAnswer,
    govern_answer,
    govern_sanitized_decision,
)
from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationUnavailableError,
    SanitizedPrivateDecision,
)


def _decision(rank: str = "stable") -> SanitizedPrivateDecision:
    return SanitizedPrivateDecision(
        existence_rank=rank,
        dominant_constraint="constraint:retention",
        next_gate="gate:review",
        confidence_band="confidence:high",
        explanation_code="explanation:stable",
        policy_version="policy:v1",
    )


def test_legacy_public_governor_math_entrypoint_fails_closed() -> None:
    with pytest.raises(PrivateEvaluationUnavailableError) as exc_info:
        govern_answer(answer="content", compatibility=0.9)

    assert str(exc_info.value) == "private_evaluation_unavailable"


def test_sanitized_governance_result_exposes_no_private_math_fields() -> None:
    assert tuple(field.name for field in fields(SanitizedGovernedAnswer)) == (
        "rank",
        "policy",
        "policy_label",
        "policy_description",
        "dominant_constraint",
        "next_gate",
        "confidence_band",
        "explanation_code",
        "policy_version",
        "repair_prompt",
    )

    forbidden = {
        "fate",
        "fate_vector",
        "reward",
        "maturity",
        "threshold",
        "weights",
        "calibration",
        "raw_score",
        "intermediate",
    }
    assert {field.name for field in fields(SanitizedGovernedAnswer)}.isdisjoint(forbidden)


def test_sanitized_private_decision_drives_public_policy_only() -> None:
    result = govern_sanitized_decision("answer", _decision())

    assert result.rank.value == "stable"
    assert result.policy == "accept"
    assert result.dominant_constraint == "constraint:retention"
    assert result.confidence_band == "confidence:high"
    assert result.policy_version == "policy:v1"
    assert result.repair_prompt is None


def test_public_governor_source_does_not_import_local_math_pipeline() -> None:
    source = Path("processual_api/cgt_governor/governor.py").read_text("utf-8")
    forbidden = (
        "from .evaluator import",
        "from .reward import",
        "compute_fate_vector(",
        "maturity_score(",
        "cgt_reward(",
        "premature_speed_risk(",
        "mature_speed_value(",
    )
    for token in forbidden:
        assert token not in source
