"""Independent task-sufficiency evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SufficiencyStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    SUFFICIENT = "sufficient"
    UNVERIFIED = "unverified"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class TaskSufficiencyEvidence:
    status: SufficiencyStatus = SufficiencyStatus.NOT_REQUIRED
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")

    def as_risk_signals(self) -> dict[str, float]:
        if self.status == SufficiencyStatus.INSUFFICIENT:
            return {"task_insufficient": 1.0}
        if self.status == SufficiencyStatus.UNVERIFIED:
            return {"task_sufficiency_unverified": 1.0}
        return {}
