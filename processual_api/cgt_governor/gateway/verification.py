"""External factual and execution verification evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VerificationStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


@dataclass(frozen=True)
class VerificationEvidence:
    factual: VerificationStatus = VerificationStatus.NOT_REQUIRED
    execution: VerificationStatus = VerificationStatus.NOT_REQUIRED
    factual_confidence: float | None = None
    execution_confidence: float | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("factual_confidence", self.factual_confidence),
            ("execution_confidence", self.execution_confidence),
        ):
            if value is not None and not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")

    def as_risk_signals(self) -> dict[str, float]:
        signals: dict[str, float] = {}
        if self.factual == VerificationStatus.CONTRADICTED:
            signals["factual_contradiction"] = 1.0
        elif self.factual == VerificationStatus.UNVERIFIED:
            signals["factual_unverified"] = 1.0
        if self.execution == VerificationStatus.CONTRADICTED:
            signals["execution_contradiction"] = 1.0
        elif self.execution == VerificationStatus.UNVERIFIED:
            signals["execution_unverified"] = 1.0
        return signals
