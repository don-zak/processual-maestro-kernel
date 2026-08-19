from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationRequest,
    SanitizedPrivateDecision,
)
from processual_api.integrations.private_evaluation_runtime import bind_private_evaluation_provider
from processual_api.routers import cgt_governor_router
from processual_api.routers.private_evaluation import (
    PrivateEvaluationEnvelope,
    PrivateEvaluationResponse,
    evaluate_private_request,
)


class _Provider:
    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        assert request.formation_ref == "formation:123"
        assert request.evidence_ref == "evidence:456"
        assert request.context_ref == "context:789"
        return SanitizedPrivateDecision(
            existence_rank="B",
            dominant_constraint="constraint.none",
            next_gate="gate.review",
            confidence_band="medium",
            explanation_code="private-evaluation-ok",
            policy_version="policy.v1",
        )


def _request(app: FastAPI) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/cgt/govern/evaluate", "headers": [], "app": app})


def _envelope() -> PrivateEvaluationEnvelope:
    return PrivateEvaluationEnvelope(
        formation_ref="formation:123",
        evidence_ref="evidence:456",
        context_ref="context:789",
        evaluated_at="2026-08-19T12:00:00Z",
    )


def test_private_evaluation_route_returns_exact_sanitized_surface() -> None:
    app = FastAPI()
    bind_private_evaluation_provider(app, _Provider())

    response = evaluate_private_request(_envelope(), _request(app))

    assert isinstance(response, PrivateEvaluationResponse)
    assert set(response.model_dump()) == {
        "existence_rank",
        "dominant_constraint",
        "next_gate",
        "confidence_band",
        "explanation_code",
        "policy_version",
    }


def test_private_evaluation_route_is_default_deny_without_provider() -> None:
    app = FastAPI()

    with pytest.raises(HTTPException) as exc_info:
        evaluate_private_request(_envelope(), _request(app))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "private_evaluation_unavailable"


def test_private_evaluation_route_rejects_invalid_reference_without_echo() -> None:
    app = FastAPI()
    invalid = PrivateEvaluationEnvelope(
        formation_ref="secret value with spaces must not echo",
        evidence_ref="evidence:456",
        context_ref="context:789",
        evaluated_at="2026-08-19T12:00:00Z",
    )

    with pytest.raises(HTTPException) as exc_info:
        evaluate_private_request(invalid, _request(app))

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "private_evaluation_contract_violation"
    assert invalid.formation_ref not in str(exc_info.value.detail)


def test_private_evaluation_route_source_has_no_raw_math_or_private_imports() -> None:
    source = Path("processual_api/routers/private_evaluation.py").read_text("utf-8")
    forbidden = (
        "cgtlib.private",
        "processual_api.private_integrations",
        "private_integrations",
        "fate_vector",
        "raw_score",
        "compatibility:",
        "coherence:",
        "threshold",
        "weight",
        "equation",
        "analyze_cgt",
        "govern_answer",
    )
    assert all(token not in source for token in forbidden)


def test_private_evaluation_route_keeps_evaluation_quota_guard() -> None:
    source = Path("processual_api/routers/private_evaluation.py").read_text("utf-8")
    assert '@router.post("/cgt/govern/evaluate"' in source
    assert 'Depends(require_quota("evaluation"))' in source


def test_private_evaluation_route_is_registered_on_governor_router() -> None:
    paths = {getattr(route, "path", "") for route in cgt_governor_router.routes}
    assert "/cgt/govern/evaluate" in paths
