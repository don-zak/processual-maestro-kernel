"""Distributed capacity isolation for durable execution domains."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .durable import ExecutionPriority


class DomainCapacitySaturatedError(RuntimeError):
    """Raised when a durable execution domain cannot acquire capacity in time."""


class DomainCapacityLeaseLostError(RuntimeError):
    """Raised when a live capacity reservation can no longer be renewed."""


@dataclass(frozen=True, slots=True)
class DomainCapacityPolicy:
    global_limit: int
    domain_limits: Mapping[str, int]
    emergency_reserve: int = 0

    def __post_init__(self) -> None:
        if self.global_limit < 1:
            raise ValueError("global_limit must be at least 1")
        if self.emergency_reserve < 0 or self.emergency_reserve >= self.global_limit:
            raise ValueError("emergency_reserve must be between 0 and global_limit - 1")
        if not self.domain_limits:
            raise ValueError("at least one domain limit is required")
        for domain, limit in self.domain_limits.items():
            if not domain.strip():
                raise ValueError("domain names cannot be empty")
            if limit < 1:
                raise ValueError("domain limits must be at least 1")

    def limit_for(self, domain: str) -> int:
        try:
            return int(self.domain_limits[domain])
        except KeyError as exc:
            raise ValueError(f"unconfigured execution domain: {domain}") from exc


@dataclass(frozen=True, slots=True)
class DomainCapacityReservation:
    lease_id: str
    domain: str
    priority: ExecutionPriority


@dataclass(frozen=True, slots=True)
class DomainCapacityDecision:
    admitted: bool
    global_used: int
    domain_used: int
    reason: str = ""


class DomainCapacityBackend(Protocol):
    async def reserve(
        self,
        *,
        reservation: DomainCapacityReservation,
        global_limit: int,
        domain_limit: int,
        emergency_reserve: int,
        lease_seconds: float,
    ) -> DomainCapacityDecision: ...

    async def renew(
        self,
        reservation: DomainCapacityReservation,
        *,
        lease_seconds: float,
    ) -> bool: ...

    async def release(self, reservation: DomainCapacityReservation) -> None: ...


class InMemoryDomainCapacityBackend:
    """Single-process reference backend for tests and development."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._leases: dict[str, tuple[float, str, ExecutionPriority]] = {}

    def _cleanup(self, now: float) -> None:
        expired = [lease_id for lease_id, value in self._leases.items() if value[0] <= now]
        for lease_id in expired:
            self._leases.pop(lease_id, None)

    async def reserve(
        self,
        *,
        reservation: DomainCapacityReservation,
        global_limit: int,
        domain_limit: int,
        emergency_reserve: int,
        lease_seconds: float,
    ) -> DomainCapacityDecision:
        async with self._lock:
            now = time.monotonic()
            self._cleanup(now)
            global_used = len(self._leases)
            domain_used = sum(1 for _, domain, _ in self._leases.values() if domain == reservation.domain)
            if global_used >= global_limit:
                return DomainCapacityDecision(False, global_used, domain_used, "global")
            if domain_used >= domain_limit:
                return DomainCapacityDecision(False, global_used, domain_used, "domain")
            if (
                reservation.priority is not ExecutionPriority.EMERGENCY
                and global_used >= global_limit - emergency_reserve
            ):
                return DomainCapacityDecision(False, global_used, domain_used, "emergency_reserve")
            self._leases[reservation.lease_id] = (
                now + lease_seconds,
                reservation.domain,
                reservation.priority,
            )
            return DomainCapacityDecision(True, global_used + 1, domain_used + 1)

    async def renew(
        self,
        reservation: DomainCapacityReservation,
        *,
        lease_seconds: float,
    ) -> bool:
        async with self._lock:
            now = time.monotonic()
            self._cleanup(now)
            current = self._leases.get(reservation.lease_id)
            if current is None or current[1] != reservation.domain:
                return False
            self._leases[reservation.lease_id] = (
                now + lease_seconds,
                current[1],
                current[2],
            )
            return True

    async def release(self, reservation: DomainCapacityReservation) -> None:
        async with self._lock:
            self._leases.pop(reservation.lease_id, None)


_REDIS_RESERVE_SCRIPT = """
local now_parts = redis.call('TIME')
local now = tonumber(now_parts[1]) * 1000 + math.floor(tonumber(now_parts[2]) / 1000)
local lease_ms = tonumber(ARGV[1])
local lease_id = ARGV[2]
local global_limit = tonumber(ARGV[3])
local domain_limit = tonumber(ARGV[4])
local emergency_reserve = tonumber(ARGV[5])
local is_emergency = tonumber(ARGV[6])
local expiry = now + lease_ms

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)

local global_used = redis.call('ZCARD', KEYS[1])
local domain_used = redis.call('ZCARD', KEYS[2])
if global_used >= global_limit then
    return {0, global_used, domain_used, 1}
end
if domain_used >= domain_limit then
    return {0, global_used, domain_used, 2}
end
if is_emergency == 0 and global_used >= (global_limit - emergency_reserve) then
    return {0, global_used, domain_used, 3}
end

redis.call('ZADD', KEYS[1], expiry, lease_id)
redis.call('ZADD', KEYS[2], expiry, lease_id)
local ttl = math.max(math.ceil(lease_ms / 1000) * 2, 10)
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
return {1, global_used + 1, domain_used + 1, 0}
"""

_REDIS_RENEW_SCRIPT = """
local now_parts = redis.call('TIME')
local now = tonumber(now_parts[1]) * 1000 + math.floor(tonumber(now_parts[2]) / 1000)
local lease_ms = tonumber(ARGV[1])
local lease_id = ARGV[2]
local expiry = now + lease_ms

local global_expiry = tonumber(redis.call('ZSCORE', KEYS[1], lease_id))
local domain_expiry = tonumber(redis.call('ZSCORE', KEYS[2], lease_id))
if (not global_expiry) or global_expiry <= now or (not domain_expiry) or domain_expiry <= now then
    redis.call('ZREM', KEYS[1], lease_id)
    redis.call('ZREM', KEYS[2], lease_id)
    return 0
end
redis.call('ZADD', KEYS[1], expiry, lease_id)
redis.call('ZADD', KEYS[2], expiry, lease_id)
return 1
"""

_REDIS_RELEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""


class RedisDomainCapacityBackend:
    """Redis lease backend shared by all worker processes and nodes."""

    def __init__(self, redis_client, *, prefix: str = "{maestro-durable-capacity}") -> None:
        self._redis = redis_client
        self._prefix = prefix.rstrip(":")

    def _keys(self, domain: str) -> tuple[str, str]:
        return (
            f"{self._prefix}:global",
            f"{self._prefix}:domain:{domain}",
        )

    async def reserve(
        self,
        *,
        reservation: DomainCapacityReservation,
        global_limit: int,
        domain_limit: int,
        emergency_reserve: int,
        lease_seconds: float,
    ) -> DomainCapacityDecision:
        keys = self._keys(reservation.domain)
        result = await self._redis.eval(
            _REDIS_RESERVE_SCRIPT,
            2,
            *keys,
            max(int(lease_seconds * 1000), 1),
            reservation.lease_id,
            global_limit,
            domain_limit,
            emergency_reserve,
            1 if reservation.priority is ExecutionPriority.EMERGENCY else 0,
        )
        reason_code = int(result[3])
        reason = {1: "global", 2: "domain", 3: "emergency_reserve"}.get(reason_code, "")
        return DomainCapacityDecision(
            admitted=int(result[0]) == 1,
            global_used=int(result[1]),
            domain_used=int(result[2]),
            reason=reason,
        )

    async def renew(
        self,
        reservation: DomainCapacityReservation,
        *,
        lease_seconds: float,
    ) -> bool:
        result = await self._redis.eval(
            _REDIS_RENEW_SCRIPT,
            2,
            *self._keys(reservation.domain),
            max(int(lease_seconds * 1000), 1),
            reservation.lease_id,
        )
        return int(result) == 1

    async def release(self, reservation: DomainCapacityReservation) -> None:
        await self._redis.eval(
            _REDIS_RELEASE_SCRIPT,
            2,
            *self._keys(reservation.domain),
            reservation.lease_id,
        )


class DomainCapacityController:
    """Acquire and renew domain capacity without changing durable job attempts."""

    def __init__(
        self,
        *,
        backend: DomainCapacityBackend,
        policy: DomainCapacityPolicy,
        lease_seconds: float = 30.0,
        wait_seconds: float = 1.0,
        retry_seconds: float = 0.025,
    ) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if wait_seconds < 0:
            raise ValueError("wait_seconds cannot be negative")
        if retry_seconds <= 0:
            raise ValueError("retry_seconds must be positive")
        self._backend = backend
        self._policy = policy
        self._lease_seconds = lease_seconds
        self._wait_seconds = wait_seconds
        self._retry_seconds = retry_seconds

    async def acquire(
        self,
        *,
        domain: str,
        priority: ExecutionPriority,
    ) -> DomainCapacityReservation:
        domain_limit = self._policy.limit_for(domain)
        reservation = DomainCapacityReservation(
            lease_id=uuid.uuid4().hex,
            domain=domain,
            priority=priority,
        )
        deadline = time.monotonic() + self._wait_seconds
        last_reason = "capacity"
        while True:
            decision = await self._backend.reserve(
                reservation=reservation,
                global_limit=self._policy.global_limit,
                domain_limit=domain_limit,
                emergency_reserve=self._policy.emergency_reserve,
                lease_seconds=self._lease_seconds,
            )
            if decision.admitted:
                return reservation
            last_reason = decision.reason or "capacity"
            if time.monotonic() >= deadline:
                raise DomainCapacitySaturatedError(
                    f"durable execution capacity saturated: {last_reason}"
                )
            await asyncio.sleep(self._retry_seconds)

    async def renew(self, reservation: DomainCapacityReservation) -> None:
        renewed = await self._backend.renew(
            reservation,
            lease_seconds=self._lease_seconds,
        )
        if not renewed:
            raise DomainCapacityLeaseLostError("durable execution capacity lease lost")

    async def release(self, reservation: DomainCapacityReservation) -> None:
        await self._backend.release(reservation)
