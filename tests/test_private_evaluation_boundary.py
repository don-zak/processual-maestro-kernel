from __future__ import annotations

from pathlib import Path

import pytest

from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationContractViolation,
    PrivateEvaluationRequest,
    PrivateEvaluationUnavailable,
    SanitizedPrivateDecision,
    boundary_contract_version,
    evaluate_through_private_boundary,
    validate_private_evaluation_request,
    validate_sanitized_private_decision,
)


class _Provider:
    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        assert request.formation_ref == "formation:abc-123"
        return SanitizedPrivateDecision(
            existence_rank="rank:A",
            dominant_constraint="constraint:retention",
            next_gate="gate:review",
            confidence_band="confidence:high",
            explanation_code="explanation:stable",
            policy_version="policy:v1",
        )


class _LeakingProvider:
    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        raise RuntimeError("SECRET_WEIGHT=0.913 proprietary_equation=x+y private/path")


def test_boundary_contract_is_versioned_and_public_safe() -> None:
    assert boundary_contract_version() == "private-evaluation-boundary/v1"

    source = Path("processual_api/integrations/private_evaluation_boundary.py").read_text("utf-8")
    forbidden = (
        "processual_api.private_integrations",
        "cgtlib.private",
        "private_integrations",
        "from ..private",
        "import_module(",
        "find_spec(",
    )
    for token in forbidden:
        assert token not in source


def test_request_is_reference_only_and_rejects_unbounded_content() -> None:
    request = PrivateEvaluationRequest(
        formation_ref="formation:abc-123",
        evidence_ref="evidence:def-456",
        context_ref="context:ghi-789",
        evaluated_at="2026-08-19T12:00:00Z",
    )
    assert validate_private_evaluation_request(request) == request

    with pytest.raises(PrivateEvaluationContractViolation):
        validate_private_evaluation_request(
            PrivateEvaluationRequest(
                formation_ref="equation=x+y weight=0.91",
                evidence_ref="evidence:def-456",
                context_ref="context:ghi-789",
                evaluated_at="2026-08-19T12:00:00Z",
            )
        )


def test_result_surface_is_exactly_six_sanitized_fields() -> None:
    decision = SanitizedPrivateDecision(
        existence_rank="rank:A",
        dominant_constraint="constraint:retention",
        next_gate="gate:review",
        confidence_band="confidence:high",
        explanation_code="explanation:stable",
        policy_version="policy:v1",
    )
    assert validate_sanitized_private_decision(decision) == decision
    assert tuple(decision.__dataclass_fields__) == (
        "existence_rank",
        "dominant_constraint",
        "next_gate",
        "confidence_band",
        "explanation_code",
        "policy_version",
    )


def test_provider_failure_does_not_leak_private_exception_text() -> None:
    request = PrivateEvaluationRequest(
        formation_ref="formation:abc-123",
        evidence_ref="evidence:def-456",
        context_ref="context:ghi-789",
        evaluated_at="2026-08-19T12:00:00Z",
    )

    with pytest.raises(PrivateEvaluationUnavailable) as exc_info:
        evaluate_through_private_boundary(_LeakingProvider(), request)

    rendered = str(exc_info.value)
    assert rendered == "private_evaluation_unavailable"
    assert "SECRET_WEIGHT" not in rendered
    assert "0.913" not in rendered
    assert "equation" not in rendered
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is None


def test_success_path_returns_only_validated_public_decision() -> None:
    request = PrivateEvaluationRequest(
        formation_ref="formation:abc-123",
        evidence_ref="evidence:def-456",
        context_ref="context:ghi-789",
        evaluated_at="2026-08-19T12:00:00Z",
    )
    result = evaluate_through_private_boundary(_Provider(), request)
    assert result.existence_rank == "rank:A"
    assert result.policy_version == "policy:v1"
