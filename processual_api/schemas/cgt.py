from pydantic import BaseModel


class FateView(BaseModel):
    stability: float
    hybridity: float
    distortion: float
    extinction: float
    collapse: float
    flourishing: float
    rank: str
    rank_label_ar: str = ""
    recommendation: str = ""


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
    view: FateView | None = None
