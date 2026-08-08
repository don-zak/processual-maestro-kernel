"""Deterministic adaptive concurrency decisions for durable execution.

The controller is intentionally isolated from worker startup. It converts
observed latency and error pressure into a recommended concurrency limit, but
callers must explicitly opt in to applying that recommendation.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdaptiveConcurrencyPolicy:
    minimum: int = 1
    maximum: int = 8
    additive_step: int = 1
    decrease_ratio: float = 0.5
    latency_target_ms: float = 250.0
    error_rate_threshold: float = 0.05
    recovery_windows: int = 3
    pressure_windows: int = 2
    healthy_latency_ratio: float = 0.9
    ewma_alpha: float = 0.25

    def __post_init__(self) -> None:
        if self.minimum < 1:
            raise ValueError("minimum must be at least 1")
        if self.maximum < self.minimum:
            raise ValueError("maximum must be greater than or equal to minimum")
        if self.additive_step < 1:
            raise ValueError("additive_step must be at least 1")
        if not 0 < self.decrease_ratio < 1:
            raise ValueError("decrease_ratio must be between 0 and 1")
        if self.latency_target_ms <= 0:
            raise ValueError("latency_target_ms must be positive")
        if not 0 <= self.error_rate_threshold <= 1:
            raise ValueError("error_rate_threshold must be between 0 and 1")
        if self.recovery_windows < 1 or self.pressure_windows < 1:
            raise ValueError("window counts must be at least 1")
        if not 0 < self.healthy_latency_ratio <= 1:
            raise ValueError("healthy_latency_ratio must be between 0 and 1")
        if not 0 < self.ewma_alpha <= 1:
            raise ValueError("ewma_alpha must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class AdaptiveConcurrencySample:
    requests: int
    latency_p95_ms: float
    errors: int = 0
    timeouts: int = 0
    rate_limited: int = 0


class AdaptiveConcurrencyController:
    """AIMD-style controller with EWMA latency and hysteresis.

    Rate limits and timeouts are treated as hard pressure and reduce the limit
    immediately. Elevated latency or ordinary error rate must persist for the
    configured pressure window before a decrease. Healthy samples must persist
    for the recovery window before an additive increase.
    """

    def __init__(
        self,
        policy: AdaptiveConcurrencyPolicy | None = None,
        *,
        initial_limit: int | None = None,
    ) -> None:
        self._policy = policy or AdaptiveConcurrencyPolicy()
        chosen = self._policy.minimum if initial_limit is None else initial_limit
        if not self._policy.minimum <= chosen <= self._policy.maximum:
            raise ValueError("initial_limit must be within policy bounds")
        self._current_limit = chosen
        self._latency_ewma_ms: float | None = None
        self._healthy_streak = 0
        self._pressure_streak = 0

    @property
    def current_limit(self) -> int:
        return self._current_limit

    @property
    def latency_ewma_ms(self) -> float | None:
        return self._latency_ewma_ms

    def observe(self, sample: AdaptiveConcurrencySample) -> int:
        if not self._valid_sample(sample):
            self._healthy_streak = 0
            self._pressure_streak = 0
            return self._current_limit

        self._update_latency(sample.latency_p95_ms)
        hard_pressure = sample.timeouts > 0 or sample.rate_limited > 0
        error_rate = sample.errors / sample.requests
        soft_pressure = (
            error_rate >= self._policy.error_rate_threshold
            or self._latency_ewma_ms is not None
            and self._latency_ewma_ms > self._policy.latency_target_ms
        )

        if hard_pressure:
            self._healthy_streak = 0
            self._pressure_streak = 0
            self._decrease()
            return self._current_limit

        if soft_pressure:
            self._healthy_streak = 0
            self._pressure_streak += 1
            if self._pressure_streak >= self._policy.pressure_windows:
                self._pressure_streak = 0
                self._decrease()
            return self._current_limit

        self._pressure_streak = 0
        healthy_threshold = self._policy.latency_target_ms * self._policy.healthy_latency_ratio
        if self._latency_ewma_ms is not None and self._latency_ewma_ms <= healthy_threshold:
            self._healthy_streak += 1
            if self._healthy_streak >= self._policy.recovery_windows:
                self._healthy_streak = 0
                self._increase()
        else:
            self._healthy_streak = 0
        return self._current_limit

    def _increase(self) -> None:
        self._current_limit = min(
            self._current_limit + self._policy.additive_step,
            self._policy.maximum,
        )

    def _decrease(self) -> None:
        reduced = math.floor(self._current_limit * self._policy.decrease_ratio)
        self._current_limit = max(reduced, self._policy.minimum)

    def _update_latency(self, latency_p95_ms: float) -> None:
        if self._latency_ewma_ms is None:
            self._latency_ewma_ms = latency_p95_ms
            return
        alpha = self._policy.ewma_alpha
        self._latency_ewma_ms = alpha * latency_p95_ms + (1 - alpha) * self._latency_ewma_ms

    @staticmethod
    def _valid_sample(sample: AdaptiveConcurrencySample) -> bool:
        counts = (sample.requests, sample.errors, sample.timeouts, sample.rate_limited)
        if sample.requests <= 0 or any(value < 0 for value in counts):
            return False
        if sample.errors > sample.requests:
            return False
        if sample.timeouts > sample.requests or sample.rate_limited > sample.requests:
            return False
        return math.isfinite(sample.latency_p95_ms) and sample.latency_p95_ms >= 0


class AdaptiveConcurrencyGate:
    """Opt-in dynamic gate driven by an adaptive concurrency controller.

    The gate limits concurrent worker iterations without cancelling work that is
    already active. Limit increases wake blocked workers immediately; decreases
    take effect naturally as active iterations complete.
    """

    def __init__(self, controller: AdaptiveConcurrencyController) -> None:
        self._controller = controller
        self._active = 0
        self._condition = asyncio.Condition()

    @property
    def current_limit(self) -> int:
        return self._controller.current_limit

    @property
    def active(self) -> int:
        return self._active

    async def acquire(self) -> None:
        async with self._condition:
            await self._condition.wait_for(
                lambda: self._active < self._controller.current_limit
            )
            self._active += 1

    async def release(self) -> None:
        async with self._condition:
            if self._active <= 0:
                raise RuntimeError("adaptive concurrency gate released without acquire")
            self._active -= 1
            self._condition.notify_all()

    async def observe(self, sample: AdaptiveConcurrencySample) -> int:
        async with self._condition:
            previous = self._controller.current_limit
            current = self._controller.observe(sample)
            if current != previous:
                self._condition.notify_all()
            return current
