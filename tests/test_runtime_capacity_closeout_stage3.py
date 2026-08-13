from __future__ import annotations

import json

import jwt
import pytest
from starlette.requests import Request

import processual_api.middleware.runtime_capacity as capacity_module
from processual_api.middleware.runtime_capacity import (
    CapacityDecision,
    CapacityPolicy,
    CapacityReservation,
    RedisCapacityBackend,
    _capacity_authority_response,
    _capacity_response,
    _lease_heartbeat,
    _request_actor_key,
    _request_weight,
)


def _request(
    path: str,
    *,
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers or [],
            "scheme": "http",
            "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
        }
    )


def _policy(**overrides) -> CapacityPolicy:
    values = {
        "enabled": True,
        "global_limit_ocu": 40,
        "actor_limit_ocu": 12,
        "lease_seconds": 120,
        "wait_ms": 250,
        "retry_ms": 25,
        "route_weights": {},
    }
    values.update(overrides)
    return CapacityPolicy(**values)


def test_capacity_policy_from_env_parses_and_clamps(monkeypatch) -> None:
    monkeypatch.setenv("CAPACITY_GUARD_ENABLED", "false")
    monkeypatch.setenv("CAPACITY_GLOBAL_LIMIT_OCU", "0")
    monkeypatch.setenv("CAPACITY_ACTOR_LIMIT_OCU", "-4")
    monkeypatch.setenv("CAPACITY_LEASE_SECONDS", "1")
    monkeypatch.setenv("CAPACITY_WAIT_MS", "-1")
    monkeypatch.setenv("CAPACITY_RETRY_MS", "1")
    monkeypatch.setenv(
        "CAPACITY_ROUTE_WEIGHTS_JSON",
        json.dumps({"/custom": 7, "/minimum": 0}),
    )

    policy = CapacityPolicy.from_env()

    assert policy.enabled is False
    assert policy.global_limit_ocu == 1
    assert policy.actor_limit_ocu == 1
    assert policy.lease_seconds == 5
    assert policy.wait_ms == 0
    assert policy.retry_ms == 5
    assert policy.route_weights == {"/custom": 7, "/minimum": 1}


def test_capacity_policy_from_env_ignores_invalid_route_weights(monkeypatch) -> None:
    monkeypatch.setenv("CAPACITY_ROUTE_WEIGHTS_JSON", "not-json")
    assert CapacityPolicy.from_env().route_weights == {}

    monkeypatch.setenv("CAPACITY_ROUTE_WEIGHTS_JSON", "[]")
    assert CapacityPolicy.from_env().route_weights == {}


class FakeRedis:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.calls = []

    async def eval(self, *args):
        self.calls.append(args)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_redis_capacity_backend_maps_reserve_renew_and_release(monkeypatch) -> None:
    redis = FakeRedis([[0, 9, 4, 2], 1, 1])
    backend = RedisCapacityBackend(redis)
    monkeypatch.setattr(capacity_module.time, "time", lambda: 100.0)

    decision = await backend.reserve(
        lease_id="lease-1",
        weight=3,
        actor_key="customer:a",
        global_limit=10,
        actor_limit=5,
        lease_seconds=30,
    )
    reservation = CapacityReservation("lease-1", 3, "customer:a")

    assert decision == CapacityDecision(False, 9, 4, "actor")
    assert await backend.renew(reservation, lease_seconds=30) is True
    await backend.release(reservation)

    assert len(redis.calls) == 3
    reserve_call = redis.calls[0]
    assert reserve_call[1] == 4
    assert reserve_call[-7:] == (100000, 130000, 3, 10, 5, "lease-1", "1")
    assert "actor:customer:a:expiry" in reserve_call[4]
    assert redis.calls[1][-2:] == ("lease-1", "1")
    assert redis.calls[2][-2:] == ("lease-1", "1")


@pytest.mark.asyncio
async def test_redis_capacity_backend_supports_global_only_reservation(monkeypatch) -> None:
    redis = FakeRedis([[1, 2, 0, 0], 0])
    backend = RedisCapacityBackend(redis)
    monkeypatch.setattr(capacity_module.time, "time", lambda: 50.0)

    decision = await backend.reserve(
        lease_id="lease-global",
        weight=2,
        actor_key=None,
        global_limit=10,
        actor_limit=3,
        lease_seconds=5,
    )
    renewed = await backend.renew(
        CapacityReservation("lease-global", 2, None),
        lease_seconds=5,
    )

    assert decision == CapacityDecision(True, 2, 0, "")
    assert renewed is False
    assert redis.calls[0][-1] == "0"
    assert "actor:none:expiry" in redis.calls[0][4]


def test_request_actor_key_prefers_valid_bearer_subject() -> None:
    token = jwt.encode(
        {"sub": "  Customer-A  "},
        capacity_module.settings.jwt_secret,
        algorithm=capacity_module.settings.jwt_algorithm,
    )
    request = _request(
        "/workflows",
        headers=[
            (b"authorization", f"Bearer {token}".encode()),
            (b"x-api-key", b"fallback-secret"),
        ],
    )

    actor = _request_actor_key(request)

    assert actor is not None
    assert actor.startswith("customer:")
    assert "Customer-A" not in actor
    assert "fallback-secret" not in actor


def test_request_actor_key_falls_back_to_api_key_after_bad_bearer() -> None:
    request = _request(
        "/workflows",
        headers=[
            (b"authorization", b"Bearer definitely-invalid"),
            (b"x-api-key", b"fallback-secret"),
        ],
    )

    actor = _request_actor_key(request)

    assert actor is not None
    assert actor.startswith("api-key:")
    assert "fallback-secret" not in actor
    assert _request_actor_key(_request("/workflows")) is None


def test_request_weight_covers_overrides_and_branch_defaults() -> None:
    policy = _policy(route_weights={"/custom": 9})

    assert _request_weight(_request("/custom", method="POST"), policy) == 9
    assert _request_weight(_request("/anything", method="HEAD"), policy) == 1
    assert _request_weight(_request("/cgt/govern", method="POST"), policy) == 3
    assert _request_weight(
        _request(
            "/workflows",
            method="POST",
            headers=[(b"content-length", b"invalid")],
        ),
        policy,
    ) == 2
    assert _request_weight(_request("/other", method="POST"), policy) == 2


def test_capacity_responses_expose_safe_operational_metadata() -> None:
    policy = _policy(global_limit_ocu=20, actor_limit_ocu=6)
    actor_response = _capacity_response(
        decision=CapacityDecision(False, 18, 6, "actor"),
        policy=policy,
        weight=3,
    )
    global_response = _capacity_response(
        decision=CapacityDecision(False, 20, 0, "global"),
        policy=policy,
        weight=2,
    )
    authority_response = _capacity_authority_response()

    actor_payload = json.loads(actor_response.body)
    global_payload = json.loads(global_response.body)
    authority_payload = json.loads(authority_response.body)

    assert actor_response.status_code == 429
    assert actor_payload["actor_used_ocu"] == 6
    assert actor_payload["actor_limit_ocu"] == 6
    assert actor_response.headers["x-maestro-capacity-reason"] == "actor"
    assert "actor_used_ocu" not in global_payload
    assert authority_response.status_code == 503
    assert authority_payload["capacity_reason"] == "lease_lost"


class NeverRenewBackend:
    async def renew(self, reservation, *, lease_seconds: int) -> bool:
        assert reservation.lease_id == "lost"
        assert lease_seconds == 6
        return False


@pytest.mark.asyncio
async def test_lease_heartbeat_raises_when_authority_is_lost(monkeypatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(capacity_module.asyncio, "sleep", no_sleep)

    with pytest.raises(RuntimeError, match="lease lost"):
        await _lease_heartbeat(
            backend=NeverRenewBackend(),
            reservation=CapacityReservation("lost", 1, None),
            lease_seconds=6,
        )
