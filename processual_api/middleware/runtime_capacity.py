"""Runtime operational-capacity admission control.

This protects the platform from excessive simultaneous work independently of
commercial subscription quotas. Redis is used when available so reservations
are shared across workers; development/test environments fall back to an
in-process atomic backend.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from processual_api.cache.redis import get_redis
from processual_api.middleware.runtime_capacity_metrics import (
    RUNTIME_CAPACITY_ACCOUNTING,
)
from processual_api.settings import settings


@dataclass(frozen=True, slots=True)
class CapacityPolicy:
    enabled: bool
    global_limit_ocu: int
    actor_limit_ocu: int
    lease_seconds: int
    wait_ms: int
    retry_ms: int
    route_weights: dict[str, int]

    @classmethod
    def from_env(cls) -> CapacityPolicy:
        raw_overrides = os.environ.get("CAPACITY_ROUTE_WEIGHTS_JSON", "").strip()
        route_weights: dict[str, int] = {}
        if raw_overrides:
            try:
                parsed = json.loads(raw_overrides)
                if isinstance(parsed, dict):
                    route_weights = {
                        str(path): max(int(weight), 1)
                        for path, weight in parsed.items()
                    }
            except (TypeError, ValueError, json.JSONDecodeError):
                route_weights = {}

        return cls(
            enabled=os.environ.get("CAPACITY_GUARD_ENABLED", "true").lower() == "true",
            global_limit_ocu=max(int(os.environ.get("CAPACITY_GLOBAL_LIMIT_OCU", "40")), 1),
            actor_limit_ocu=max(int(os.environ.get("CAPACITY_ACTOR_LIMIT_OCU", "12")), 1),
            lease_seconds=max(int(os.environ.get("CAPACITY_LEASE_SECONDS", "120")), 5),
            wait_ms=max(int(os.environ.get("CAPACITY_WAIT_MS", "250")), 0),
            retry_ms=max(int(os.environ.get("CAPACITY_RETRY_MS", "25")), 5),
            route_weights=route_weights,
        )


@dataclass(frozen=True, slots=True)
class CapacityReservation:
    lease_id: str
    weight: int
    actor_key: str | None


@dataclass(frozen=True, slots=True)
class CapacityDecision:
    admitted: bool
    global_used: int
    actor_used: int
    reason: str = ""


class CapacityBackend(Protocol):
    async def reserve(
        self,
        *,
        lease_id: str,
        weight: int,
        actor_key: str | None,
        global_limit: int,
        actor_limit: int,
        lease_seconds: int,
    ) -> CapacityDecision: ...

    async def renew(
        self,
        reservation: CapacityReservation,
        *,
        lease_seconds: int,
    ) -> bool: ...

    async def release(self, reservation: CapacityReservation) -> None: ...


class InMemoryCapacityBackend:
    """Atomic single-process backend used when Redis is unavailable."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._leases: dict[str, tuple[float, int, str | None]] = {}

    def _cleanup(self, now: float) -> None:
        expired = [lease_id for lease_id, entry in self._leases.items() if entry[0] <= now]
        for lease_id in expired:
            self._leases.pop(lease_id, None)

    def _usage(self, actor_key: str | None) -> tuple[int, int]:
        global_used = sum(weight for _expiry, weight, _actor in self._leases.values())
        actor_used = 0
        if actor_key is not None:
            actor_used = sum(
                weight
                for _expiry, weight, actor in self._leases.values()
                if actor == actor_key
            )
        return global_used, actor_used

    async def reserve(
        self,
        *,
        lease_id: str,
        weight: int,
        actor_key: str | None,
        global_limit: int,
        actor_limit: int,
        lease_seconds: int,
    ) -> CapacityDecision:
        async with self._lock:
            now = time.monotonic()
            self._cleanup(now)
            global_used, actor_used = self._usage(actor_key)
            if global_used + weight > global_limit:
                return CapacityDecision(False, global_used, actor_used, "global")
            if actor_key is not None and actor_used + weight > actor_limit:
                return CapacityDecision(False, global_used, actor_used, "actor")
            self._leases[lease_id] = (now + lease_seconds, weight, actor_key)
            return CapacityDecision(
                True,
                global_used + weight,
                actor_used + weight if actor_key is not None else actor_used,
            )

    async def renew(
        self,
        reservation: CapacityReservation,
        *,
        lease_seconds: int,
    ) -> bool:
        async with self._lock:
            now = time.monotonic()
            self._cleanup(now)
            current = self._leases.get(reservation.lease_id)
            if current is None:
                return False
            _expiry, weight, actor_key = current
            if weight != reservation.weight or actor_key != reservation.actor_key:
                return False
            self._leases[reservation.lease_id] = (
                now + lease_seconds,
                weight,
                actor_key,
            )
            return True

    async def release(self, reservation: CapacityReservation) -> None:
        async with self._lock:
            self._leases.pop(reservation.lease_id, None)


_REDIS_RESERVE_SCRIPT = """
local now = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local weight = tonumber(ARGV[3])
local global_limit = tonumber(ARGV[4])
local actor_limit = tonumber(ARGV[5])
local lease_id = ARGV[6]
local has_actor = ARGV[7] == '1'

local function cleanup(zkey, hkey)
    local expired = redis.call('ZRANGEBYSCORE', zkey, '-inf', now)
    for _, id in ipairs(expired) do
        redis.call('ZREM', zkey, id)
        redis.call('HDEL', hkey, id)
    end
end

local function total(hkey)
    local values = redis.call('HVALS', hkey)
    local sum = 0
    for _, value in ipairs(values) do
        sum = sum + tonumber(value)
    end
    return sum
end

cleanup(KEYS[1], KEYS[2])
local global_used = total(KEYS[2])
if global_used + weight > global_limit then
    return {0, global_used, 0, 1}
end

local actor_used = 0
if has_actor then
    cleanup(KEYS[3], KEYS[4])
    actor_used = total(KEYS[4])
    if actor_used + weight > actor_limit then
        return {0, global_used, actor_used, 2}
    end
end

redis.call('ZADD', KEYS[1], expiry, lease_id)
redis.call('HSET', KEYS[2], lease_id, weight)
redis.call('EXPIRE', KEYS[1], math.max(math.ceil((expiry - now) / 1000) * 2, 10))
redis.call('EXPIRE', KEYS[2], math.max(math.ceil((expiry - now) / 1000) * 2, 10))
if has_actor then
    redis.call('ZADD', KEYS[3], expiry, lease_id)
    redis.call('HSET', KEYS[4], lease_id, weight)
    redis.call('EXPIRE', KEYS[3], math.max(math.ceil((expiry - now) / 1000) * 2, 10))
    redis.call('EXPIRE', KEYS[4], math.max(math.ceil((expiry - now) / 1000) * 2, 10))
end
return {1, global_used + weight, actor_used + (has_actor and weight or 0), 0}
"""

_REDIS_RENEW_SCRIPT = """
local now = tonumber(ARGV[1])
local expiry = tonumber(ARGV[2])
local lease_id = ARGV[3]
local has_actor = ARGV[4] == '1'

local function remove_lease()
    redis.call('ZREM', KEYS[1], lease_id)
    redis.call('HDEL', KEYS[2], lease_id)
    if has_actor then
        redis.call('ZREM', KEYS[3], lease_id)
        redis.call('HDEL', KEYS[4], lease_id)
    end
end

local global_expiry = tonumber(redis.call('ZSCORE', KEYS[1], lease_id))
local global_weight = redis.call('HGET', KEYS[2], lease_id)
if (not global_expiry) or global_expiry <= now or (not global_weight) then
    remove_lease()
    return 0
end

if has_actor then
    local actor_expiry = tonumber(redis.call('ZSCORE', KEYS[3], lease_id))
    local actor_weight = redis.call('HGET', KEYS[4], lease_id)
    if (not actor_expiry) or actor_expiry <= now or (not actor_weight) then
        remove_lease()
        return 0
    end
    if tonumber(actor_weight) ~= tonumber(global_weight) then
        remove_lease()
        return 0
    end
end

local ttl = math.max(math.ceil((expiry - now) / 1000) * 2, 10)
redis.call('ZADD', KEYS[1], expiry, lease_id)
redis.call('EXPIRE', KEYS[1], ttl)
redis.call('EXPIRE', KEYS[2], ttl)
if has_actor then
    redis.call('ZADD', KEYS[3], expiry, lease_id)
    redis.call('EXPIRE', KEYS[3], ttl)
    redis.call('EXPIRE', KEYS[4], ttl)
end
return 1
"""

_REDIS_RELEASE_SCRIPT = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('HDEL', KEYS[2], ARGV[1])
if ARGV[2] == '1' then
    redis.call('ZREM', KEYS[3], ARGV[1])
    redis.call('HDEL', KEYS[4], ARGV[1])
end
return 1
"""


class RedisCapacityBackend:
    def __init__(self, redis_client) -> None:
        self._redis = redis_client

    @staticmethod
    def _keys(actor_key: str | None) -> list[str]:
        prefix = "{maestro-capacity}"
        actor = actor_key or "none"
        return [
            f"{prefix}:global:expiry",
            f"{prefix}:global:weights",
            f"{prefix}:actor:{actor}:expiry",
            f"{prefix}:actor:{actor}:weights",
        ]

    async def reserve(
        self,
        *,
        lease_id: str,
        weight: int,
        actor_key: str | None,
        global_limit: int,
        actor_limit: int,
        lease_seconds: int,
    ) -> CapacityDecision:
        now_ms = int(time.time() * 1000)
        expiry_ms = now_ms + lease_seconds * 1000
        result = await self._redis.eval(
            _REDIS_RESERVE_SCRIPT,
            4,
            *self._keys(actor_key),
            now_ms,
            expiry_ms,
            weight,
            global_limit,
            actor_limit,
            lease_id,
            "1" if actor_key is not None else "0",
        )
        admitted = int(result[0]) == 1
        reason_code = int(result[3])
        reason = "global" if reason_code == 1 else "actor" if reason_code == 2 else ""
        return CapacityDecision(admitted, int(result[1]), int(result[2]), reason)

    async def renew(
        self,
        reservation: CapacityReservation,
        *,
        lease_seconds: int,
    ) -> bool:
        now_ms = int(time.time() * 1000)
        expiry_ms = now_ms + lease_seconds * 1000
        result = await self._redis.eval(
            _REDIS_RENEW_SCRIPT,
            4,
            *self._keys(reservation.actor_key),
            now_ms,
            expiry_ms,
            reservation.lease_id,
            "1" if reservation.actor_key is not None else "0",
        )
        return int(result) == 1

    async def release(self, reservation: CapacityReservation) -> None:
        await self._redis.eval(
            _REDIS_RELEASE_SCRIPT,
            4,
            *self._keys(reservation.actor_key),
            reservation.lease_id,
            "1" if reservation.actor_key is not None else "0",
        )


_LOCAL_BACKEND = InMemoryCapacityBackend()


def _request_actor_key(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            import jwt

            payload = jwt.decode(auth[7:], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            subject = payload.get("sub")
            if isinstance(subject, str) and subject.strip():
                normalized = subject.strip().lower().encode("utf-8")
                return "customer:" + hashlib.sha256(normalized).hexdigest()[:32]
        except Exception:
            pass

    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        return "api-key:" + hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:32]
    return None


def _request_weight(request: Request, policy: CapacityPolicy) -> int:
    path = request.url.path
    if path in policy.route_weights:
        return policy.route_weights[path]
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return 1
    if path == "/cgt/govern/batch":
        return 4
    if path.startswith("/cgt/govern"):
        return 3
    if path == "/workflows":
        try:
            content_length = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            content_length = 0
        return 3 if content_length >= 20_000 else 2
    return 2


def _capacity_response(
    *,
    decision: CapacityDecision,
    policy: CapacityPolicy,
    weight: int,
) -> Response:
    payload = {
        "detail": "Operational capacity is temporarily saturated. Retry shortly.",
        "capacity_reason": decision.reason,
        "requested_ocu": weight,
        "global_used_ocu": decision.global_used,
        "global_limit_ocu": policy.global_limit_ocu,
    }
    if decision.reason == "actor":
        payload["actor_used_ocu"] = decision.actor_used
        payload["actor_limit_ocu"] = policy.actor_limit_ocu
    return Response(
        status_code=429,
        content=json.dumps(payload),
        media_type="application/json",
        headers={
            "Retry-After": "1",
            "X-Maestro-Capacity-Reason": decision.reason or "saturated",
        },
    )


def _capacity_authority_response() -> Response:
    return Response(
        status_code=503,
        content=json.dumps(
            {
                "detail": "Operational capacity authority was lost during execution.",
                "capacity_reason": "lease_lost",
            }
        ),
        media_type="application/json",
        headers={
            "Retry-After": "1",
            "X-Maestro-Capacity-Reason": "lease_lost",
        },
    )


async def _lease_heartbeat(
    *,
    backend: CapacityBackend,
    reservation: CapacityReservation,
    lease_seconds: int,
) -> None:
    """Renew one active reservation until cancelled or authority is lost."""

    interval_seconds = max(min(lease_seconds / 3, lease_seconds - 1), 1.0)
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            renewed = await backend.renew(
                reservation,
                lease_seconds=lease_seconds,
            )
        except Exception:
            renewed = False
        if not renewed:
            raise RuntimeError("runtime capacity lease lost")
        RUNTIME_CAPACITY_ACCOUNTING.renewed(
            lease_id=reservation.lease_id,
            renewed_at=time.monotonic(),
            lease_seconds=lease_seconds,
        )


class RuntimeCapacityMiddleware(BaseHTTPMiddleware):
    """Weighted admission control with bounded wait and crash-safe leases."""

    _EXEMPT_PATHS = {"/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next):
        policy = CapacityPolicy.from_env()
        if not policy.enabled or request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        weight = _request_weight(request, policy)
        actor_key = _request_actor_key(request)
        lease_id = uuid.uuid4().hex
        reservation = CapacityReservation(lease_id, weight, actor_key)

        redis_client = await get_redis()
        backend: CapacityBackend
        if redis_client is not None:
            backend = RedisCapacityBackend(redis_client)
        else:
            if settings.is_production:
                RUNTIME_CAPACITY_ACCOUNTING.rejected(reason="backend_unavailable")
                return Response(
                    status_code=503,
                    content=json.dumps(
                        {
                            "detail": "Operational capacity authority is unavailable.",
                            "capacity_reason": "backend_unavailable",
                        }
                    ),
                    media_type="application/json",
                    headers={"Retry-After": "1"},
                )
            backend = _LOCAL_BACKEND

        deadline = time.monotonic() + policy.wait_ms / 1000
        decision = CapacityDecision(False, 0, 0, "global")
        backpressure_recorded = False
        while True:
            decision = await backend.reserve(
                lease_id=lease_id,
                weight=weight,
                actor_key=actor_key,
                global_limit=policy.global_limit_ocu,
                actor_limit=policy.actor_limit_ocu,
                lease_seconds=policy.lease_seconds,
            )
            if decision.admitted:
                break
            if not backpressure_recorded:
                RUNTIME_CAPACITY_ACCOUNTING.backpressured(reason=decision.reason)
                backpressure_recorded = True
            if time.monotonic() >= deadline:
                RUNTIME_CAPACITY_ACCOUNTING.rejected(reason=decision.reason)
                return _capacity_response(decision=decision, policy=policy, weight=weight)
            await asyncio.sleep(policy.retry_ms / 1000)

        admitted_at = time.monotonic()
        RUNTIME_CAPACITY_ACCOUNTING.admitted(
            lease_id=lease_id,
            weight_ocu=weight,
            admitted_at=admitted_at,
            lease_seconds=policy.lease_seconds,
        )
        response: Response | None = None
        heartbeat_task = asyncio.create_task(
            _lease_heartbeat(
                backend=backend,
                reservation=reservation,
                lease_seconds=policy.lease_seconds,
            )
        )
        request_task = asyncio.create_task(call_next(request))
        try:
            done, _pending = await asyncio.wait(
                {request_task, heartbeat_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat_task in done:
                heartbeat_error = heartbeat_task.exception()
                if heartbeat_error is not None:
                    request_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await request_task
                    RUNTIME_CAPACITY_ACCOUNTING.rejected(reason="lease_lost")
                    response = _capacity_authority_response()
                    return response

            response = await request_task
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task
            response.headers["X-Maestro-Capacity-OCU"] = str(weight)
            response.headers["X-Maestro-Capacity-Global"] = (
                f"{decision.global_used}/{policy.global_limit_ocu}"
            )
            return response
        finally:
            for task in (heartbeat_task, request_task):
                if not task.done():
                    task.cancel()
            for task in (heartbeat_task, request_task):
                if not task.done():
                    with suppress(asyncio.CancelledError):
                        await task

            finished_at = time.monotonic()
            release_failed = False
            try:
                await backend.release(reservation)
            except Exception:
                # Charge the reservation through its latest TTL when explicit release fails.
                release_failed = True
            accounting_finished_at = finished_at
            if release_failed:
                lease_expiry = RUNTIME_CAPACITY_ACCOUNTING.lease_expires_at(lease_id=lease_id)
                if lease_expiry is not None:
                    accounting_finished_at = lease_expiry
            units = RUNTIME_CAPACITY_ACCOUNTING.released(
                lease_id=lease_id,
                finished_at=accounting_finished_at,
            )
            if response is not None:
                response.headers["X-Maestro-Capacity-OCU-Seconds"] = f"{units:.6f}"
                if release_failed:
                    response.headers["X-Maestro-Capacity-Lease"] = "expires"
