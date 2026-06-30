from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(StrEnum):
    FATE_EXTINCTION_RISK = "FATE_EXTINCTION_RISK"
    FATE_DISTORTION_SPIKE = "FATE_DISTORTION_SPIKE"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    SECURITY_CRYPTO_FAILURE = "SECURITY_CRYPTO_FAILURE"
    DEPLOYMENT_READY = "DEPLOYMENT_READY"


@dataclass(frozen=True, slots=True)
class AlertPayload:
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    description: str
    fields: dict[str, str] = field(default_factory=dict)
    workflow_id: str | None = None
