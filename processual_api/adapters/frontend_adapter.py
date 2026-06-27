from __future__ import annotations

from pydantic import BaseModel


class FateView(BaseModel):
    stability: float
    hybridity: float
    distortion: float
    extinction: float
    collapse: float
    flourishing: float
    rank: str
    rank_label_ar: str
    recommendation: str


class WorkflowView(BaseModel):
    workflow_id: str
    status: str
    fate: FateView | None = None
    metrics: dict[str, float] = {}
    warnings: list[str] = []


class GovernanceView(BaseModel):
    workflow_id: str
    runtime_mode: str
    policy: str
    certification_level: str = "controlled_ready"
    warnings: list[str] = []


def fate_vector_to_frontend(fate_dict: dict[str, float], rank: str) -> FateView:
    from .cgt_adapter import arabic_rank_label, recommendation_for_rank

    rank_enum = None
    try:
        from cgtlib import ExistenceRank

        rank_enum = ExistenceRank(rank)
    except ValueError:
        rank_enum = None
    return FateView(
        stability=fate_dict.get("stability", 0.0),
        hybridity=fate_dict.get("hybridity", 0.0),
        distortion=fate_dict.get("distortion", 0.0),
        extinction=fate_dict.get("extinction", 0.0),
        collapse=fate_dict.get("collapse", 0.0),
        flourishing=fate_dict.get("flourishing", 0.0),
        rank=rank,
        rank_label_ar=arabic_rank_label(rank_enum) if rank_enum else rank,
        recommendation=recommendation_for_rank(rank_enum) if rank_enum else rank,
    )


def workflow_to_frontend(workflow_id: str, status: str, fate: FateView | None = None) -> WorkflowView:
    return WorkflowView(
        workflow_id=workflow_id,
        status=status,
        fate=fate,
    )


def governance_to_frontend(workflow_id: str, runtime_mode: str, policy: str) -> GovernanceView:
    return GovernanceView(
        workflow_id=workflow_id,
        runtime_mode=runtime_mode,
        policy=policy,
        certification_level="controlled_ready",
    )
