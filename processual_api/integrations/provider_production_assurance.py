"""Stage 4 provider and production assurance contracts.

This module is intentionally pure and fail-closed. It evaluates observed
provider health, circuit-breaker state, routing eligibility, resilience/SLO
signals, and release evidence without making provider network calls or enabling
production connectivity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Final

PROVIDER_ASSURANCE_VERSION: Final = "2026-08-b4-provider-assurance-v1"
PRODUCTION_PROVIDER_EXECUTION_ENABLED: Final = False
PRODUCTION_RELEASE_ENABLED: Final = False


class ProviderHealth(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class ProviderObservation:
    provider_id: str
    observed_at: datetime
    success_rate: Decimal
    p95_latency_ms: int
    consecutive_failures: int
    evidence_reference: str

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be blank")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not Decimal("0") <= self.success_rate <= Decimal("1"):
            raise ValueError("success_rate must be between 0 and 1")
        if self.p95_latency_ms < 0:
            raise ValueError("p95_latency_ms must not be negative")
        if self.consecutive_failures < 0:
            raise ValueError("consecutive_failures must not be negative")
        if not self.evidence_reference.strip():
            raise ValueError("evidence_reference must not be blank")


@dataclass(frozen=True, slots=True)
class ProviderPolicy:
    minimum_success_rate: Decimal = Decimal("0.99")
    maximum_p95_latency_ms: int = 3000
    open_after_failures: int = 5
    observation_ttl_seconds: int = 300

    def __post_init__(self) -> None:
        if not Decimal("0") < self.minimum_success_rate <= Decimal("1"):
            raise ValueError("minimum_success_rate must be in (0, 1]")
        if self.maximum_p95_latency_ms <= 0:
            raise ValueError("maximum_p95_latency_ms must be positive")
        if self.open_after_failures <= 0:
            raise ValueError("open_after_failures must be positive")
        if self.observation_ttl_seconds <= 0:
            raise ValueError("observation_ttl_seconds must be positive")


def classify_provider_health(
    observation: ProviderObservation | None,
    *,
    now: datetime,
    policy: ProviderPolicy = ProviderPolicy(),
) -> ProviderHealth:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if observation is None:
        return ProviderHealth.UNKNOWN
    if now - observation.observed_at > timedelta(seconds=policy.observation_ttl_seconds):
        return ProviderHealth.UNKNOWN
    if observation.consecutive_failures >= policy.open_after_failures:
        return ProviderHealth.UNAVAILABLE
    if observation.success_rate < policy.minimum_success_rate:
        return ProviderHealth.DEGRADED
    if observation.p95_latency_ms > policy.maximum_p95_latency_ms:
        return ProviderHealth.DEGRADED
    return ProviderHealth.HEALTHY


def circuit_state_for_observation(
    observation: ProviderObservation | None,
    *,
    now: datetime,
    policy: ProviderPolicy = ProviderPolicy(),
) -> CircuitState:
    health = classify_provider_health(observation, now=now, policy=policy)
    if health in {ProviderHealth.UNAVAILABLE, ProviderHealth.UNKNOWN}:
        return CircuitState.OPEN
    if health is ProviderHealth.DEGRADED:
        return CircuitState.HALF_OPEN
    return CircuitState.CLOSED


@dataclass(frozen=True, slots=True)
class RoutingCandidate:
    provider_id: str
    priority: int
    approved: bool
    observation: ProviderObservation | None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id must not be blank")
        if self.priority < 0:
            raise ValueError("priority must not be negative")


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    selected_provider_id: str | None
    eligible_provider_ids: tuple[str, ...]
    rejected_provider_ids: tuple[str, ...]
    reason: str


def choose_provider(
    candidates: Iterable[RoutingCandidate],
    *,
    now: datetime,
    policy: ProviderPolicy = ProviderPolicy(),
) -> RoutingDecision:
    eligible: list[RoutingCandidate] = []
    rejected: list[str] = []
    for candidate in candidates:
        circuit = circuit_state_for_observation(
            candidate.observation,
            now=now,
            policy=policy,
        )
        if candidate.approved and circuit is CircuitState.CLOSED:
            eligible.append(candidate)
        else:
            rejected.append(candidate.provider_id)

    eligible.sort(key=lambda item: (item.priority, item.provider_id))
    if not eligible:
        return RoutingDecision(
            selected_provider_id=None,
            eligible_provider_ids=(),
            rejected_provider_ids=tuple(sorted(rejected)),
            reason="no_approved_healthy_provider",
        )
    return RoutingDecision(
        selected_provider_id=eligible[0].provider_id,
        eligible_provider_ids=tuple(item.provider_id for item in eligible),
        rejected_provider_ids=tuple(sorted(rejected)),
        reason="selected_highest_priority_approved_healthy_provider",
    )


@dataclass(frozen=True, slots=True)
class ResilienceEvidence:
    backup_verified_at: datetime | None
    restore_verified_at: datetime | None
    recovery_point_objective_minutes: int
    recovery_time_objective_minutes: int
    measured_restore_minutes: int | None

    def __post_init__(self) -> None:
        for value in (
            self.recovery_point_objective_minutes,
            self.recovery_time_objective_minutes,
        ):
            if value <= 0:
                raise ValueError("RPO/RTO targets must be positive")
        for value in (self.backup_verified_at, self.restore_verified_at):
            if value is not None and value.tzinfo is None:
                raise ValueError("resilience evidence timestamps must be timezone-aware")
        if self.measured_restore_minutes is not None and self.measured_restore_minutes < 0:
            raise ValueError("measured_restore_minutes must not be negative")

    @property
    def ready(self) -> bool:
        return (
            self.backup_verified_at is not None
            and self.restore_verified_at is not None
            and self.measured_restore_minutes is not None
            and self.measured_restore_minutes <= self.recovery_time_objective_minutes
        )


@dataclass(frozen=True, slots=True)
class SloEvidence:
    availability_target: Decimal
    measured_availability: Decimal
    latency_target_ms: int
    measured_p95_latency_ms: int

    def __post_init__(self) -> None:
        for name, value in (
            ("availability_target", self.availability_target),
            ("measured_availability", self.measured_availability),
        ):
            if not Decimal("0") <= value <= Decimal("1"):
                raise ValueError(f"{name} must be between 0 and 1")
        if self.latency_target_ms <= 0 or self.measured_p95_latency_ms < 0:
            raise ValueError("latency values are invalid")

    @property
    def met(self) -> bool:
        return (
            self.measured_availability >= self.availability_target
            and self.measured_p95_latency_ms <= self.latency_target_ms
        )


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    release_id: str
    commit_sha: str
    generated_at: datetime
    ci_passed: bool
    security_checks_passed: bool
    resilience: ResilienceEvidence
    slo: SloEvidence
    artifact_digest: str

    def __post_init__(self) -> None:
        if not self.release_id.strip() or not self.commit_sha.strip():
            raise ValueError("release_id and commit_sha must not be blank")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if len(self.artifact_digest) != 64:
            raise ValueError("artifact_digest must be a sha256 hex digest")
        try:
            int(self.artifact_digest, 16)
        except ValueError as exc:
            raise ValueError("artifact_digest must be a sha256 hex digest") from exc

    @property
    def production_ready(self) -> bool:
        return (
            self.ci_passed
            and self.security_checks_passed
            and self.resilience.ready
            and self.slo.met
        )


def evidence_digest(payload: dict[str, object]) -> str:
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_release_assurance_status(evidence: ReleaseEvidence) -> dict[str, object]:
    return {
        "version": PROVIDER_ASSURANCE_VERSION,
        "release_id": evidence.release_id,
        "commit_sha": evidence.commit_sha,
        "generated_at": evidence.generated_at.astimezone(UTC).isoformat(),
        "ci_passed": evidence.ci_passed,
        "security_checks_passed": evidence.security_checks_passed,
        "resilience_ready": evidence.resilience.ready,
        "slo_met": evidence.slo.met,
        "evidence_digest": evidence_digest(asdict(evidence)),
        "artifact_digest": evidence.artifact_digest,
        "production_ready": evidence.production_ready,
        "production_provider_execution_enabled": PRODUCTION_PROVIDER_EXECUTION_ENABLED,
        "production_release_enabled": PRODUCTION_RELEASE_ENABLED,
    }


__all__ = [
    "CircuitState",
    "PRODUCTION_PROVIDER_EXECUTION_ENABLED",
    "PRODUCTION_RELEASE_ENABLED",
    "PROVIDER_ASSURANCE_VERSION",
    "ProviderHealth",
    "ProviderObservation",
    "ProviderPolicy",
    "ReleaseEvidence",
    "ResilienceEvidence",
    "RoutingCandidate",
    "RoutingDecision",
    "SloEvidence",
    "build_release_assurance_status",
    "choose_provider",
    "circuit_state_for_observation",
    "classify_provider_health",
    "evidence_digest",
]
