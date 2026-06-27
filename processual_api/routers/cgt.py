"""CGT evaluation routes — fate vector analysis and existence ranking."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/cgt", tags=["cgt"])


class CGTEvaluateRequest(BaseModel):
    transition_channel: float = 0.5
    compatibility: float = 0.5
    retention: float = 0.5
    harmony: float = 0.5
    fatigue: float = 0.3
    complexity: float = 0.3
    shock: float = 0.1
    dwell_time: float = 3.0
    carrier: float = 0.5
    diversity: float = 0.5
    novelty: float = 0.5
    lift: float = 0.0


class CGTEvaluateResponse(BaseModel):
    fate_vector: dict[str, float]
    existence_rank: str


@router.post("/evaluate", response_model=CGTEvaluateResponse)
async def evaluate_cgt(req: CGTEvaluateRequest):
    from cgtlib import classify_existence_rank, evaluate_fate_vector

    fate = evaluate_fate_vector(
        transition_channel=req.transition_channel,
        compatibility=req.compatibility,
        retention=req.retention,
        harmony=req.harmony,
        fatigue=req.fatigue,
        complexity=req.complexity,
        shock=req.shock,
        dwell_time=req.dwell_time,
        carrier=req.carrier,
        diversity=req.diversity,
        novelty=req.novelty,
        lift=req.lift,
    )
    rank = classify_existence_rank(fate)
    return CGTEvaluateResponse(
        fate_vector={
            "stability": fate.stability,
            "hybridity": fate.hybridity,
            "distortion": fate.distortion,
            "extinction": fate.extinction,
            "collapse": fate.collapse,
            "flourishing": fate.flourishing,
            "balance": fate.balance,
        },
        existence_rank=rank.value,
    )
