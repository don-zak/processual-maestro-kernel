"""Low-cardinality operational accounting for runtime capacity.

One Maestro operational statistical unit is defined as one OCU-second: one
operational capacity unit held for one second. This accounting is deliberately
separate from commercial quota and billing usage.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    from prometheus_client import Counter, Gauge

    ACTIVE_OCU = Gauge(
        "maestro_capacity_active_ocu",
        "Process-local operational capacity units held by admitted work.",
    )
    OPERATIONAL_STATISTICAL_UNITS = Counter(
        "maestro_capacity_operational_statistical_units",
        "Accumulated Maestro operational statistical units; 1 unit = 1 OCU-second.",
    )
    ADMISSIONS = Counter(
        "maestro_capacity_admissions",
        "Runtime-capacity admission outcomes.",
        ["outcome", "reason"],
    )
    BACKPRESSURE = Counter(
        "maestro_capacity_backpressure",
        "Requests that encountered runtime-capacity backpressure.",
        ["reason"],
    )
    LEASE_EXPIRATIONS = Counter(
        "maestro_capacity_lease_expirations",
        "Capacity reservations whose accounting reached the lease expiry boundary.",
    )
    _PROMETHEUS_AVAILABLE = True
except Exception:
    _PROMETHEUS_AVAILABLE = False


@dataclass(frozen=True, slots=True)
class CapacityLeaseAccounting:
    weight_ocu: int
    admitted_at: float
    lease_expires_at: float


def operational_statistical_units(
    *,
    weight_ocu: int,
    admitted_at: float,
    finished_at: float,
    lease_expires_at: float,
) -> float:
    """Return occupied OCU-seconds, capped at the crash-safe lease boundary."""

    occupied_until = min(max(finished_at, admitted_at), lease_expires_at)
    duration_seconds = max(occupied_until - admitted_at, 0.0)
    return float(weight_ocu) * duration_seconds


class RuntimeCapacityAccounting:
    """Idempotent per-process accounting for admitted capacity leases."""

    def __init__(self) -> None:
        self._leases: dict[str, CapacityLeaseAccounting] = {}

    def admitted(
        self,
        *,
        lease_id: str,
        weight_ocu: int,
        admitted_at: float,
        lease_seconds: int,
    ) -> bool:
        if lease_id in self._leases:
            return False
        self._leases[lease_id] = CapacityLeaseAccounting(
            weight_ocu=weight_ocu,
            admitted_at=admitted_at,
            lease_expires_at=admitted_at + lease_seconds,
        )
        if _PROMETHEUS_AVAILABLE:
            ACTIVE_OCU.inc(weight_ocu)
            ADMISSIONS.labels(outcome="admitted", reason="none").inc()
        return True

    def backpressured(self, *, reason: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            BACKPRESSURE.labels(reason=_bounded_reason(reason)).inc()

    def rejected(self, *, reason: str) -> None:
        if _PROMETHEUS_AVAILABLE:
            ADMISSIONS.labels(outcome="rejected", reason=_bounded_reason(reason)).inc()

    def released(self, *, lease_id: str, finished_at: float) -> float:
        lease = self._leases.pop(lease_id, None)
        if lease is None:
            return 0.0

        units = operational_statistical_units(
            weight_ocu=lease.weight_ocu,
            admitted_at=lease.admitted_at,
            finished_at=finished_at,
            lease_expires_at=lease.lease_expires_at,
        )
        if _PROMETHEUS_AVAILABLE:
            ACTIVE_OCU.dec(lease.weight_ocu)
            OPERATIONAL_STATISTICAL_UNITS.inc(units)
            if finished_at >= lease.lease_expires_at:
                LEASE_EXPIRATIONS.inc()
        return units


def _bounded_reason(reason: str) -> str:
    if reason in {"global", "actor", "backend_unavailable"}:
        return reason
    return "unknown"


RUNTIME_CAPACITY_ACCOUNTING = RuntimeCapacityAccounting()
