from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..auth.security import require_quota
from ..integrations.private_evaluation_boundary import (
    PrivateEvaluationContractViolationError,
    PrivateEvaluationRequest,
    PrivateEvaluationUnavailableError,
    SanitizedPrivateDecision,
    evaluate_through_private_boundary,
)
from ..integrations.private_evaluation_runtime import private_evaluation_provider_from_request

router = APIRouter(tags=["cgt-governor"])


class PrivateEvaluationEnvelope(BaseModel):
    formation_ref: str
    evidence_ref: str
    context_ref: str
    evaluated_at: str

    def to_contract(self) -> PrivateEvaluationRequest:
        return PrivateEvaluationRequest(
            formation_ref=self.formation_ref,
            evidence_ref=self.evidence_ref,
            context_ref=self.context_ref,
            evaluated_at=self.evaluated_at,
        )


class PrivateEvaluationResponse(BaseModel):
    existence_rank: str
    dominant_constraint: str
    next_gate: str
    confidence_band: str
    explanation_code: str
    policy_version: str

    @classmethod
    def from_contract(cls, decision: SanitizedPrivateDecision) -> PrivateEvaluationResponse:
        return cls(
            existence_rank=decision.existence_rank,
            dominant_constraint=decision.dominant_constraint,
            next_gate=decision.next_gate,
            confidence_band=decision.confidence_band,
            explanation_code=decision.explanation_code,
            policy_version=decision.policy_version,
        )


def evaluate_private_request(envelope: PrivateEvaluationEnvelope, request: Request) -> PrivateEvaluationResponse:
    try:
        contract_request = envelope.to_contract()
    except PrivateEvaluationContractViolationError:
        raise HTTPException(status_code=422, detail="private_evaluation_contract_violation") from None

    try:
        provider = private_evaluation_provider_from_request(request)
        decision = evaluate_through_private_boundary(provider, contract_request)
    except PrivateEvaluationUnavailableError:
        raise HTTPException(status_code=503, detail="private_evaluation_unavailable") from None
    except PrivateEvaluationContractViolationError:
        raise HTTPException(status_code=502, detail="private_evaluation_contract_violation") from None

    return PrivateEvaluationResponse.from_contract(decision)


@router.post("/cgt/govern/evaluate", response_model=PrivateEvaluationResponse)
async def evaluate_private(
    envelope: PrivateEvaluationEnvelope,
    request: Request,
    _current_user: dict = Depends(require_quota("evaluation")),
) -> PrivateEvaluationResponse:
    return evaluate_private_request(envelope, request)
