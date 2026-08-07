from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request

import processual_api.middleware.runtime_capacity as capacity_module
from processual_api.middleware.runtime_capacity import (
    CapacityPolicy,
    CapacityReservation,
    InMemoryCapacityBackend,
    _request_actor_key,
    _request_weight,
)
from processual_api.middleware.runtime_capacity_metrics import (
    RuntimeCapacityAccounting,
    operational_statistical_units,
)


@pytest.mark.asyncio
async def test_global_capacity_reservation_is_atomic() -> None:
    backend = InMemoryCapacityBackend()

    async def reserve(index: int):
        return await backend.reserve(
            lease_id=f"lease-{index}",
            weight=3,
            actor_key=f"actor-{index}",
            global_limit=10,
            actor_limit=10,
            lease_seconds=60,
        )

    decisions = await asyncio.gather(*(reserve(index) for index in range(12)))

    admitted = [decision for decision in decisions if decision.admitted]
    rejected = [decision for decision in decisions if not decision.admitted]
    assert len(admitted) == 3
    assert rejected
    assert all(decision.reason == "global" for decision in rejected)
    assert max(decision.global_used for decision in admitted) == 9


@pytest.mark.asyncio
async def test_actor_capacity_is_shared_across_requests() -> None:
    backend = InMemoryCapacityBackend()

    first = await backend.reserve(
        lease_id="one",
        weight=4,
        actor_key="customer:a",
        global_limit=40,
        actor_limit=6,
        lease_seconds=60,
    )
    second = await backend.reserve(
        lease_id="two",
        weight=3,
        actor_key="customer:a",
        global_limit=40,
        actor_limit=6,
        lease_seconds=60,
    )
    other_actor = await backend.reserve(
        lease_id="three",
        weight=3,
        actor_key="customer:b",
        global_limit=40,
        actor_limit=6,
        lease_seconds=60,
    )

    assert first.admitted is True
    assert second.admitted is False
    assert second.reason == "actor"
    assert other_actor.admitted is True


@pytest.mark.asyncio
async def test_release_restores_capacity() -> None:
    backend = InMemoryCapacityBackend()
    reservation = CapacityReservation("one", 4, "customer:a")

    first = await backend.reserve(
        lease_id=reservation.lease_id,
        weight=reservation.weight,
        actor_key=reservation.actor_key,
        global_limit=4,
        actor_limit=4,
        lease_seconds=60,
    )
    blocked = await backend.reserve(
        lease_id="two",
        weight=1,
        actor_key="customer:b",
        global_limit=4,
        actor_limit=4,
        lease_seconds=60,
    )
    await backend.release(reservation)
    retried = await backend.reserve(
        lease_id="two",
        weight=1,
        actor_key="customer:b",
        global_limit=4,
        actor_limit=4,
        lease_seconds=60,
    )

    assert first.admitted is True
    assert blocked.admitted is False
    assert retried.admitted is True


@pytest.mark.asyncio
async def test_renew_extends_in_memory_lease_without_double_charging(monkeypatch) -> None:
    backend = InMemoryCapacityBackend()
    reservation = CapacityReservation("one", 4, "customer:a")
    now = 100.0
    monkeypatch.setattr(capacity_module.time, "monotonic", lambda: now)

    admitted = await backend.reserve(
        lease_id=reservation.lease_id,
        weight=reservation.weight,
        actor_key=reservation.actor_key,
        global_limit=4,
        actor_limit=4,
        lease_seconds=5,
    )
    assert admitted.admitted is True

    now = 103.0
    assert await backend.renew(reservation, lease_seconds=5) is True

    now = 106.0
    blocked = await backend.reserve(
        lease_id="two",
        weight=1,
        actor_key="customer:b",
        global_limit=4,
        actor_limit=4,
        lease_seconds=5,
    )
    assert blocked.admitted is False
    assert blocked.global_used == 4

    await backend.release(reservation)
    retried = await backend.reserve(
        lease_id="two",
        weight=1,
        actor_key="customer:b",
        global_limit=4,
        actor_limit=4,
        lease_seconds=5,
    )
    assert retried.admitted is True


@pytest.mark.asyncio
async def test_expired_in_memory_lease_cannot_be_renewed(monkeypatch) -> None:
    backend = InMemoryCapacityBackend()
    reservation = CapacityReservation("one", 2, "customer:a")
    now = 100.0
    monkeypatch.setattr(capacity_module.time, "monotonic", lambda: now)

    await backend.reserve(
        lease_id=reservation.lease_id,
        weight=reservation.weight,
        actor_key=reservation.actor_key,
        global_limit=4,
        actor_limit=4,
        lease_seconds=5,
    )
    now = 105.0

    assert await backend.renew(reservation, lease_seconds=5) is False


def _request(path: str, *, method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers or [],
            "scheme": "http",
            "server": ("test", 80),
            "client": ("127.0.0.1", 1234),
        }
    )


def test_measured_workload_weights_are_conservative() -> None:
    policy = CapacityPolicy(
        enabled=True,
        global_limit_ocu=40,
        actor_limit_ocu=12,
        lease_seconds=120,
        wait_ms=250,
        retry_ms=25,
        route_weights={},
    )

    assert _request_weight(_request("/health/live"), policy) == 1
    assert _request_weight(_request("/workflows", method="POST"), policy) == 2
    assert _request_weight(
        _request(
            "/workflows",
            method="POST",
            headers=[(b"content-length", b"25000")],
        ),
        policy,
    ) == 3
    assert _request_weight(_request("/cgt/govern/batch", method="POST"), policy) == 4


def test_api_key_actor_is_stable_but_not_raw_secret() -> None:
    request = _request(
        "/workflows",
        method="POST",
        headers=[(b"x-api-key", b"benchmark-only-api-key")],
    )
    actor_key = _request_actor_key(request)

    assert actor_key is not None
    assert actor_key.startswith("api-key:")
    assert "benchmark-only-api-key" not in actor_key


def test_one_maestro_operational_unit_is_one_ocu_second() -> None:
    units = operational_statistical_units(
        weight_ocu=4,
        admitted_at=10.0,
        finished_at=10.25,
        lease_expires_at=20.0,
    )

    assert units == pytest.approx(1.0)


def test_operational_units_are_capped_at_lease_expiry() -> None:
    units = operational_statistical_units(
        weight_ocu=3,
        admitted_at=10.0,
        finished_at=30.0,
        lease_expires_at=15.0,
    )

    assert units == pytest.approx(15.0)


def test_operational_units_never_go_negative() -> None:
    units = operational_statistical_units(
        weight_ocu=4,
        admitted_at=10.0,
        finished_at=9.0,
        lease_expires_at=20.0,
    )

    assert units == 0.0


def test_capacity_accounting_is_idempotent_per_lease() -> None:
    accounting = RuntimeCapacityAccounting()

    assert accounting.admitted(
        lease_id="lease-ocu",
        weight_ocu=2,
        admitted_at=100.0,
        lease_seconds=10,
    ) is True
    assert accounting.admitted(
        lease_id="lease-ocu",
        weight_ocu=2,
        admitted_at=100.0,
        lease_seconds=10,
    ) is False

    assert accounting.released(lease_id="lease-ocu", finished_at=101.5) == pytest.approx(3.0)
    assert accounting.released(lease_id="lease-ocu", finished_at=102.0) == 0.0


def test_capacity_accounting_renewal_extends_ocu_window() -> None:
    accounting = RuntimeCapacityAccounting()

    assert accounting.admitted(
        lease_id="lease-renewed",
        weight_ocu=2,
        admitted_at=100.0,
        lease_seconds=10,
    ) is True
    assert accounting.lease_expires_at(lease_id="lease-renewed") == pytest.approx(110.0)
    assert accounting.renewed(
        lease_id="lease-renewed",
        renewed_at=106.0,
        lease_seconds=10,
    ) is True
    assert accounting.lease_expires_at(lease_id="lease-renewed") == pytest.approx(116.0)

    assert accounting.released(
        lease_id="lease-renewed",
        finished_at=114.0,
    ) == pytest.approx(28.0)
    assert accounting.renewed(
        lease_id="lease-renewed",
        renewed_at=115.0,
        lease_seconds=10,
    ) is False
