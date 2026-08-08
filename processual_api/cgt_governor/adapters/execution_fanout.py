"""Cross-worker operational fan-out governor for external provider calls.

Runtime request OCU protects HTTP admission. This module protects the second
layer: downstream calls spawned by an admitted request. Redis leases make the
limits shared across workers and crash-safe; development/test falls back to an
in-process backend.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol

from processual_api.cache.redis import get_redis
from processual_api.settings import settings


class ExecutionFanoutSaturatedError(RuntimeError):
    """Raised when an external provider slot cannot be admitted in time."""


class ExecutionFanoutAuthorityUnavailableError(RuntimeError):
    """Raised when production cannot reach its shared fan-out authority."""


class ExecutionFanoutLeaseLostError(RuntimeError):
    """Raised when a live provider call loses its shared lease."""


@dataclass(frozen=True, slots=True)
class ExecutionFanoutPolicy:
    enabled: bool
    global_limit: int
    provider_limit: int
    lease_seconds: int
    wait_ms: int
    retry_ms: int

    @classmethod
    def from_env(cls) -> ExecutionFanoutPolicy:
        return cls(
            enabled=os.environ.get("EXECUTION_FANOUT_ENABLED", "true").lower() == "true",
            global_limit=max(int(os.environ.get("EXECUTION_FANOUT_GLOBAL_LIMIT", "16")), 1),
            provider_limit=max(int(os.environ.get("EXECUTION_FANOUT_PROVIDER_LIMIT", "8")), 1),
            lease_seconds=max(int(os.environ.get("EXECUTION_FANOUT_LEASE_SECONDS", "180")), 5),
            wait_ms=max(int(os.environ.get("EXECUTION_FANOUT_WAIT_MS", "250")), 0),
            retry_ms=max(int(os.environ.get("EXECUTION_FANOUT_RETRY_MS", "25")), 5),
        )


@dataclass(frozen=True, slots=True)
class ExecutionFanoutReservation:
    lease_id: str
    provider_key: str


@dataclass(frozen=True, slots=True)
class ExecutionFanoutDecision:
    admitted: bool
    global_used: int
    provider_used: int
    reason: str = ""


class ExecutionFanoutBackend(Protocol):
    async def reserve(
        self,
        *,
        reservation: ExecutionFanoutReservation,
        global_limit: int,
        provider_limit: int,
        lease_seconds: int,
    ) -> ExecutionFanoutDecision: ...

    async def renew(
        self,
        reservation: ExecutionFanoutReservation,
        *,
        lease_seconds: int,
    ) -> bool: ...

    async def release(self, reservation: ExecutionFanoutReservation) -> None: ...


class InMemoryExecutionFanoutBackend:
    """Atomic single-process fallback for development and tests."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._leases: dict[str, tuple[float, str]] = {}

    def _cleanup(self, now: float) -> None:
        expired = [lease_id for lease_id, (expiry, _provider) in self._leases.items() if expiry <= now]
        for lease_id in expired:
            self._leases.pop(lease_id, None)

    async def reserve(
        self,
        *,
        reservation: ExecutionFanoutReservation,
        global_limit: int,
        provider_limit: int,
        lease_seconds: int,
    ) -> ExecutionFanoutDecision:
        async with self._lock:
            now = time.monotonic()
            self._cleanup(now)
            global_used = len(self._leases)
            provider_used = sum(
                1 for _expiry, provider in self._leases.values() if provider == reservation.provider_key
            )
            if global_used >= global_limit:
                return ExecutionFanoutDecision(False, global_used, provider_used, "global")
            if provider_used >= provider_limit:
                return ExecutionFanoutDecision(False, global_used, provider_used, "provider")
            self._leases[reservation.lease_id] = (
                now + lease_seconds,
                reservation.provider_key,
            )
            return ExecutionFanoutDecision(True, global_used + 1, provider_used + 1)

    async def renew(
        self,
        reservation: ExecutionFanoutReservation,
        *,
        lease_seconds: int,
    ) -> bool:
        async with self._lock:
            now = time.monotonic()
            self._cleanup(now)
            current = self._leases.get(reservation.lease_id)
            if current is None or current[1] != reservation.provider_key:
                return False
            self._leases[reservation.lease_id] = (now + lease_seconds, reservation.provider_key)
            return True

    async def release(self, reservation: ExecutionFanoutReservation) -> None:
        async with self._lock:
            self._leases.pop(reservation.lease_id, None)


_REDIS_RESERVE_SCRIPT = """
local now = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local lease_id = ARGV[3]
local global_limit = tonumber(ARGV[4])
local provider_limit = tonumber(ARGV[5])

redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)

local global_used = redis.call('ZCARD', KEYS[1])
local provider_used = redis.call('ZCARD', KEYS[2])
if global_used >= global_limit then
    return {0, global_used, provider_used, 1}
end
if provider_used >= provider_limit then
    return {0, global_used, provider_used, 2}
end

redis.call('ZADD', KEYS[1], expiry, lease_id)
redis.call('ZADD', KEYS[2], expiry, lease_id)
local ttl = math.max(math.ceil((expiry - now) / 1000) * 2, 10)
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
return {1, global_used + 1, provider_used + 1, 0}
"""

_REDIS_RENEW_SCRIPT = """
local now = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local lease_id = ARGV[3]

local global_expiry = tonumber(redis.call('ZSCORE', KEYS[1], lease_id))
local provider_expiry = tonumber(redis.call('ZSCORE', KEYS[2], lease_id))
if (not global_expiry) or global_expiry <= now or (not provider_expiry) or provider_expiry <= now then
    redis.call('ZREM', KEYS[1], lease_id)
    redis.call('ZREM', KEYS[2], lease_id)
    return 0
end

redis.call('ZADD', KEYS[1], expiry, lease_id)
redis.call('ZADD', KEYS[2], expiry, lease_id)
local ttl = math.max(math.ceil((expiry - now) / 1000) * 2, 10)
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
return 1
"""

_REDIS_RELEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""


class RedisExecutionFanoutBackend:
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    @staticmethod
    def _keys(provider_key: str) -> tuple[str, str]:
        prefix = "{maestro-fanout}"
        return (
            f"{prefix}:global:expiry",
            f"{prefix}:provider:{provider_key}:expiry",
        )

    async def reserve(
        self,
        *,
        reservation: ExecutionFanoutReservation,
        global_limit: int,
        provider_limit: int,
        lease_seconds: int,
    ) -> ExecutionFanoutDecision:
        now_ms = int(time.time() * 1000)
        expiry_ms = now_ms + lease_seconds * 1000
        result = await self._redis.eval(
            _REDIS_RESERVE_SCRIPT,
            2,
            *self._keys(reservation.provider_key),
            now_ms,
            expiry_ms,
            reservation.lease_id,
            global_limit,
            provider_limit,
        )
        reason_code = int(result[3])
        reason = "global" if reason_code == 1 else "provider" if reason_code == 2 else ""
        return ExecutionFanoutDecision(
            admitted=int(result[0]) == 1,
            global_used=int(result[1]),
            provider_used=int(result[2]),
            reason=reason,
        )

    async def renew(
        self,
        reservation: ExecutionFanoutReservation,
        *,
        lease_seconds: int,
    ) -> bool:
        now_ms = int(time.time() * 1000)
        expiry_ms = now_ms + lease_seconds * 1000
        result = await self._redis.eval(
            _REDIS_RENEW_SCRIPT,
            2,
            *self._keys(reservation.provider_key),
            now_ms,
            expiry_ms,
            reservation.lease_id,
        )
        return int(result) == 1

    async def release(self, reservation: ExecutionFanoutReservation) -> None:
        await self._redis.eval(
            _REDIS_RELEASE_SCRIPT,
            2,
            *self._keys(reservation.provider_key),
            reservation.lease_id,
        )


_LOCAL_BACKEND = InMemoryExecutionFanoutBackend()


def _provider_key(provider: str) -> str:
    normalized = provider.strip().lower().encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:24]


async def _heartbeat(
    *,
    backend: ExecutionFanoutBackend,
    reservation: ExecutionFanoutReservation,
    lease_seconds: int,
) -> None:
    interval_seconds = max(min(lease_seconds / 3, lease_seconds - 1), 1.0)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            renewed = await backend.renew(reservation, lease_seconds=lease_seconds)
        except Exception:
            renewed = False
        if not renewed:
            raise ExecutionFanoutLeaseLostError("execution fan-out lease lost")


async def run_with_execution_fanout[T](
    provider: str,
    operation: Callable[[], Awaitable[T]],
) -> T:
    """Run one provider operation under shared global/provider fan-out limits."""

    policy = ExecutionFanoutPolicy.from_env()
    if not policy.enabled:
        return await operation()

    redis_client = await get_redis()
    backend: ExecutionFanoutBackend
    if redis_client is not None:
        backend = RedisExecutionFanoutBackend(redis_client)
    elif settings.is_production:
        raise ExecutionFanoutAuthorityUnavailableError(
            "execution fan-out authority is unavailable"
        )
    else:
        backend = _LOCAL_BACKEND

    reservation = ExecutionFanoutReservation(
        lease_id=uuid.uuid4().hex,
        provider_key=_provider_key(provider),
    )
    deadline = time.monotonic() + policy.wait_ms / 1000
    while True:
        decision = await backend.reserve(
            reservation=reservation,
            global_limit=policy.global_limit,
            provider_limit=policy.provider_limit,
            lease_seconds=policy.lease_seconds,
        )
        if decision.admitted:
            break
        if time.monotonic() >= deadline:
            raise ExecutionFanoutSaturatedError(
                f"execution fan-out saturated: {decision.reason}"
            )
        await asyncio.sleep(policy.retry_ms / 1000)

    heartbeat_task = asyncio.create_task(
        _heartbeat(
            backend=backend,
            reservation=reservation,
            lease_seconds=policy.lease_seconds,
        )
    )
    operation_task = asyncio.create_task(operation())
    try:
        done, _pending = await asyncio.wait(
            {operation_task, heartbeat_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if heartbeat_task in done:
            heartbeat_error = heartbeat_task.exception()
            if heartbeat_error is not None:
                operation_task.cancel()
                with suppress(asyncio.CancelledError):
                    await operation_task
                raise heartbeat_error
        return await operation_task
    finally:
        for task in (heartbeat_task, operation_task):
            if not task.done():
                task.cancel()
        for task in (heartbeat_task, operation_task):
            if not task.done():
                with suppress(asyncio.CancelledError):
                    await task
        with suppress(Exception):
            await backend.release(reservation)
