from __future__ import annotations

from cgtlib import ExistenceRank, StructuralTransitionReport

_RANK_LABELS_EN = {
    ExistenceRank.FLOURISHING: "Flourishing",
    ExistenceRank.STABLE: "Stable",
    ExistenceRank.HYBRID: "Hybrid",
    ExistenceRank.DISTORTED: "Distorted",
    ExistenceRank.TRANSIENT: "Transient",
    ExistenceRank.EXTINCT: "Extinct",
}

_RANK_LABELS_AR = {
    ExistenceRank.FLOURISHING: "ازدهار",
    ExistenceRank.STABLE: "مستقر",
    ExistenceRank.HYBRID: "هجين",
    ExistenceRank.DISTORTED: "مشوّه",
    ExistenceRank.TRANSIENT: "عابر",
    ExistenceRank.EXTINCT: "مندثر",
}


def arabic_rank_label(rank: ExistenceRank) -> str:
    return _RANK_LABELS_AR.get(rank, rank.value)


def rank_label(rank: ExistenceRank, language: str = "en") -> str:
    labels = _RANK_LABELS_AR if language == "ar" else _RANK_LABELS_EN
    return labels.get(rank, rank.value)


def recommendation_for_rank(rank: ExistenceRank) -> str:
    recs = {
        ExistenceRank.FLOURISHING: "continue current trajectory",
        ExistenceRank.STABLE: "monitor for drift, maintain governance",
        ExistenceRank.HYBRID: "review handoff schemas, reduce ambiguity",
        ExistenceRank.DISTORTED: "simplify handoff schema, increase safety gates",
        ExistenceRank.TRANSIENT: "increase carrying capacity, reduce fatigue",
        ExistenceRank.EXTINCT: "immediate human intervention required",
    }
    return recs.get(rank, "review governance state")


def fate_vector_to_view(report: StructuralTransitionReport, language: str = "en") -> dict:
    fate = report.fate_vector
    rank = report.existence_rank
    if fate is None or rank is None:
        return {}
    return {
        "stability": fate.stability,
        "hybridity": fate.hybridity,
        "distortion": fate.distortion,
        "extinction": fate.extinction,
        "collapse": fate.collapse,
        "flourishing": fate.flourishing,
        "rank": rank.value,
        "rank_label": rank_label(rank, language),
        "recommendation": recommendation_for_rank(rank),
    }
