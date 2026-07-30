"""Adaptive commercial-capacity contracts for Group 2.

The policy is review-only. It calculates load state and available elastic
headroom but does not enforce limits, reject work, or mutate quota balances.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Final

ADAPTIVE_CAPACITY_VERSION: Final = "2026-07-group2-adaptive-capacity-v1"
ADAPTIVE_CAPACITY_STATUS: Final = "draft_review"

ADAPTIVE_CAPACITY_ENABLED: Final = False
ADAPTIVE_CAPACITY_MODE: Final = "observe_only"
SOFT_LIMIT_ENFORCEMENT_ENABLED: Final = False
HARD_LIMIT_ENFORCEMENT_ENABLED: Final = False
EMERGENCY_LOAD_SHEDDING_ENABLED: Final = False

GLOBAL_RUNNING_JOBS_SOFT_LIMIT: Final = 60
GLOBAL_RUNNING_JOBS_HARD_LIMIT: Final = 100
GLOBAL_RUNNING_JOBS_EMERGENCY_LIMIT: Final = 120

GLOBAL_UNITS_PER_HOUR_SOFT_LIMIT: Final = 300_000
GLOBAL_UNITS_PER_HOUR_HARD_LIMIT: Final = 500_000
GLOBAL_UNITS_PER_HOUR_EMERGENCY_LIMIT: Final = 600_000

OPEN_MAXIMUM_LOAD_RATIO: Final = 0.40
NORMAL_MAXIMUM_LOAD_RATIO: Final = 0.65
CONSTRAINED_MAXIMUM_LOAD_RATIO: Final = 0.80
PROTECTIVE_MAXIMUM_LOAD_RATIO: Final = 0.90

PROTECTIVE_EXIT_LOAD_RATIO: Final = 0.65
RECOVERY_STABILITY_SECONDS: Final = 300


class CapacityOperatingMode(StrEnum):
    OBSERVE_ONLY = "observe_only"
    ENFORCE_SOFT_LIMITS = "enforce_soft_limits"
    ENFORCE_HARD_LIMITS = "enforce_hard_limits"


class PlatformLoadState(StrEnum):
    OPEN = "open"
    NORMAL = "normal"
    CONSTRAINED = "constrained"
    PROTECTIVE = "protective"
    EMERGENCY = "emergency"


@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    running_jobs: int
    reserved_jobs: int
    queued_jobs: int
    units_per_hour: int
    worker_utilization: float
    cpu_utilization: float
    memory_utilization: float
    database_pool_utilization: float
    database_latency_p95_ratio: float
    queue_wait_p95_ratio: float
    task_latency_p95_ratio: float
    task_latency_p99_ratio: float
    error_rate_ratio: float
    retry_rate_ratio: float

    def __post_init__(self) -> None:
        count_values = (
            self.running_jobs,
            self.reserved_jobs,
            self.queued_jobs,
            self.units_per_hour,
        )
        if any(value < 0 for value in count_values):
            raise ValueError("capacity counters must not be negative")

        ratio_values = (
            self.worker_utilization,
            self.cpu_utilization,
            self.memory_utilization,
            self.database_pool_utilization,
            self.database_latency_p95_ratio,
            self.queue_wait_p95_ratio,
            self.task_latency_p95_ratio,
            self.task_latency_p99_ratio,
            self.error_rate_ratio,
            self.retry_rate_ratio,
        )
        if any(value < 0 for value in ratio_values):
            raise ValueError("capacity ratios must not be negative")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdaptiveCapacityDecision:
    state: PlatformLoadState
    governing_load_ratio: float
    shared_headroom_factor: float
    accepts_new_noncritical_work: bool
    queue_new_work: bool
    enforcement_enabled: bool
    reason: str

    def __post_init__(self) -> None:
        if self.governing_load_ratio < 0:
            raise ValueError("governing_load_ratio must not be negative")
        if not 0 <= self.shared_headroom_factor <= 1:
            raise ValueError("shared_headroom_factor must be between zero and one")
        if self.enforcement_enabled:
            raise ValueError("adaptive capacity enforcement must remain disabled")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload


def _safe_ratio(value: int, limit: int) -> float:
    if limit <= 0:
        raise ValueError("capacity limit must be positive")
    return value / limit


def governing_load_ratio(snapshot: CapacitySnapshot) -> float:
    """Use the most constrained observed resource as governing load."""

    return max(
        _safe_ratio(
            snapshot.running_jobs,
            GLOBAL_RUNNING_JOBS_HARD_LIMIT,
        ),
        _safe_ratio(
            snapshot.units_per_hour,
            GLOBAL_UNITS_PER_HOUR_HARD_LIMIT,
        ),
        snapshot.worker_utilization,
        snapshot.cpu_utilization,
        snapshot.memory_utilization,
        snapshot.database_pool_utilization,
        snapshot.database_latency_p95_ratio,
        snapshot.queue_wait_p95_ratio,
        snapshot.task_latency_p95_ratio,
        snapshot.task_latency_p99_ratio,
        snapshot.error_rate_ratio,
        snapshot.retry_rate_ratio,
    )


def classify_platform_load(
    snapshot: CapacitySnapshot,
) -> PlatformLoadState:
    ratio = governing_load_ratio(snapshot)

    if (
        snapshot.running_jobs >= GLOBAL_RUNNING_JOBS_EMERGENCY_LIMIT
        or snapshot.units_per_hour >= GLOBAL_UNITS_PER_HOUR_EMERGENCY_LIMIT
        or ratio > PROTECTIVE_MAXIMUM_LOAD_RATIO
    ):
        return PlatformLoadState.EMERGENCY
    if ratio > CONSTRAINED_MAXIMUM_LOAD_RATIO:
        return PlatformLoadState.PROTECTIVE
    if ratio > NORMAL_MAXIMUM_LOAD_RATIO:
        return PlatformLoadState.CONSTRAINED
    if ratio > OPEN_MAXIMUM_LOAD_RATIO:
        return PlatformLoadState.NORMAL
    return PlatformLoadState.OPEN


def shared_headroom_factor(state: PlatformLoadState) -> float:
    return {
        PlatformLoadState.OPEN: 1.0,
        PlatformLoadState.NORMAL: 0.75,
        PlatformLoadState.CONSTRAINED: 0.25,
        PlatformLoadState.PROTECTIVE: 0.0,
        PlatformLoadState.EMERGENCY: 0.0,
    }[state]


def decide_adaptive_capacity(
    snapshot: CapacitySnapshot,
) -> AdaptiveCapacityDecision:
    """Calculate an observe-only decision with no rejection authority."""

    state = classify_platform_load(snapshot)
    ratio = governing_load_ratio(snapshot)

    queue_new_work = state in {
        PlatformLoadState.PROTECTIVE,
        PlatformLoadState.EMERGENCY,
    }

    accepts_new_noncritical_work = state is not PlatformLoadState.EMERGENCY

    return AdaptiveCapacityDecision(
        state=state,
        governing_load_ratio=ratio,
        shared_headroom_factor=shared_headroom_factor(state),
        accepts_new_noncritical_work=accepts_new_noncritical_work,
        queue_new_work=queue_new_work,
        enforcement_enabled=ADAPTIVE_CAPACITY_ENABLED,
        reason=("observe-only adaptive capacity decision; no runtime rejection authority is enabled"),
    )


def effective_concurrency_limit(
    *,
    guaranteed_concurrency: int,
    maximum_elastic_concurrency: int,
    state: PlatformLoadState,
) -> int:
    """Calculate available concurrency without granting enforcement."""

    if guaranteed_concurrency <= 0:
        raise ValueError("guaranteed_concurrency must be positive")
    if maximum_elastic_concurrency < guaranteed_concurrency:
        raise ValueError("maximum_elastic_concurrency must be at least guaranteed")

    elastic_range = maximum_elastic_concurrency - guaranteed_concurrency
    elastic_allowance = int(elastic_range * shared_headroom_factor(state))
    return guaranteed_concurrency + elastic_allowance


def adaptive_capacity_review_payload() -> dict[str, object]:
    return {
        "version": ADAPTIVE_CAPACITY_VERSION,
        "status": ADAPTIVE_CAPACITY_STATUS,
        "enabled": ADAPTIVE_CAPACITY_ENABLED,
        "mode": ADAPTIVE_CAPACITY_MODE,
        "soft_limit_enforcement_enabled": (SOFT_LIMIT_ENFORCEMENT_ENABLED),
        "hard_limit_enforcement_enabled": (HARD_LIMIT_ENFORCEMENT_ENABLED),
        "emergency_load_shedding_enabled": (EMERGENCY_LOAD_SHEDDING_ENABLED),
        "running_jobs": {
            "soft": GLOBAL_RUNNING_JOBS_SOFT_LIMIT,
            "hard": GLOBAL_RUNNING_JOBS_HARD_LIMIT,
            "emergency": GLOBAL_RUNNING_JOBS_EMERGENCY_LIMIT,
        },
        "units_per_hour": {
            "soft": GLOBAL_UNITS_PER_HOUR_SOFT_LIMIT,
            "hard": GLOBAL_UNITS_PER_HOUR_HARD_LIMIT,
            "emergency": GLOBAL_UNITS_PER_HOUR_EMERGENCY_LIMIT,
        },
        "protective_exit_load_ratio": PROTECTIVE_EXIT_LOAD_RATIO,
        "recovery_stability_seconds": RECOVERY_STABILITY_SECONDS,
    }


__all__ = [
    "ADAPTIVE_CAPACITY_ENABLED",
    "ADAPTIVE_CAPACITY_MODE",
    "ADAPTIVE_CAPACITY_STATUS",
    "ADAPTIVE_CAPACITY_VERSION",
    "AdaptiveCapacityDecision",
    "CapacityOperatingMode",
    "CapacitySnapshot",
    "EMERGENCY_LOAD_SHEDDING_ENABLED",
    "GLOBAL_RUNNING_JOBS_EMERGENCY_LIMIT",
    "GLOBAL_RUNNING_JOBS_HARD_LIMIT",
    "GLOBAL_RUNNING_JOBS_SOFT_LIMIT",
    "GLOBAL_UNITS_PER_HOUR_EMERGENCY_LIMIT",
    "GLOBAL_UNITS_PER_HOUR_HARD_LIMIT",
    "GLOBAL_UNITS_PER_HOUR_SOFT_LIMIT",
    "HARD_LIMIT_ENFORCEMENT_ENABLED",
    "PlatformLoadState",
    "PROTECTIVE_EXIT_LOAD_RATIO",
    "RECOVERY_STABILITY_SECONDS",
    "SOFT_LIMIT_ENFORCEMENT_ENABLED",
    "adaptive_capacity_review_payload",
    "classify_platform_load",
    "decide_adaptive_capacity",
    "effective_concurrency_limit",
    "governing_load_ratio",
    "shared_headroom_factor",
]
