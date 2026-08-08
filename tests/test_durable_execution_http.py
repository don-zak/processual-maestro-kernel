import asyncio

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from processual_api.execution.durable import InMemoryDurableJobStore, JobStatus
from processual_api.execution.http import create_durable_execution_router
from processual_api.execution.pool import DurableWorkerPool, DurableWorkerPoolPolicy
from processual_api.execution.service import DurableExecutionService
from processual_api.execution.worker import DurableWorker


async def authorized() -> dict:
    return {"sub": "operator", "scopes": ["internal:execution"]}


async def denied() -> None:
    raise HTTPException(status_code=403, detail="forbidden")


def app_for(service: DurableExecutionService, authorize=authorized) -> FastAPI:
    app = FastAPI()
    app.include_router(create_durable_execution_router(service=service, authorize=authorize))
    return app


@pytest.mark.asyncio
async def test_router_requires_explicit_authorization_dependency() -> None:
    service = DurableExecutionService(store=InMemoryDurableJobStore())

    with pytest.raises(ValueError, match="requires authorization"):
        create_durable_execution_router(service=service, authorize=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_all_routes_are_blocked_by_authorization_dependency() -> None:
    service = DurableExecutionService(store=InMemoryDurableJobStore())
    transport = ASGITransport(app=app_for(service, authorize=denied))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [
            await client.get("/internal/execution/health"),
            await client.post(
                "/internal/execution/jobs",
                json={"idempotency_key": "blocked", "domain": "oss", "payload": {}},
            ),
            await client.get("/internal/execution/jobs/missing"),
            await client.post("/internal/execution/jobs/missing/cancel"),
        ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]


@pytest.mark.asyncio
async def test_submit_status_cancel_and_health_contract() -> None:
    store = InMemoryDurableJobStore()
    service = DurableExecutionService(store=store)
    transport = ASGITransport(app=app_for(service))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/internal/execution/health")
        assert health.status_code == 200
        assert health.json() == {"running": False, "state": "not_configured"}

        created = await client.post(
            "/internal/execution/jobs",
            json={
                "idempotency_key": "http-job",
                "domain": "oss",
                "payload": {"ticket": "INC-9"},
                "priority": 10,
                "max_attempts": 4,
            },
        )
        assert created.status_code == 202
        body = created.json()
        assert body["created"] is True
        assert body["job"]["status"] == "queued"
        assert body["job"]["priority"] == 10
        job_id = body["job"]["job_id"]

        status_response = await client.get(f"/internal/execution/jobs/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["idempotency_key"] == "http-job"

        cancelled = await client.post(f"/internal/execution/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["cancel_requested"] is True


@pytest.mark.asyncio
async def test_duplicate_submit_is_idempotent_and_conflict_is_409() -> None:
    service = DurableExecutionService(store=InMemoryDurableJobStore())
    transport = ASGITransport(app=app_for(service))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"idempotency_key": "same", "domain": "oss", "payload": {"value": 1}}
        first = await client.post("/internal/execution/jobs", json=payload)
        second = await client.post("/internal/execution/jobs", json=payload)
        conflict = await client.post(
            "/internal/execution/jobs",
            json={"idempotency_key": "same", "domain": "billing", "payload": {"value": 1}},
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job"]["job_id"] == second.json()["job"]["job_id"]
    assert second.json()["created"] is False
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "idempotency key conflicts with an existing durable job"


@pytest.mark.asyncio
async def test_missing_job_is_404_without_internal_error_details() -> None:
    service = DurableExecutionService(store=InMemoryDurableJobStore())
    transport = ASGITransport(app=app_for(service))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/internal/execution/jobs/secret-internal-id")

    assert response.status_code == 404
    assert response.json() == {"detail": "durable job not found"}


@pytest.mark.asyncio
async def test_http_submit_executes_through_opt_in_worker_pool() -> None:
    store = InMemoryDurableJobStore()

    async def handler(job):
        return {"handled": job.spec.payload["ticket"]}

    worker = DurableWorker(store=store, worker_id="http-worker", handlers={"oss": handler})
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.005, recovery_interval_seconds=0.01),
    )
    service = DurableExecutionService(store=store, pool=pool)
    transport = ASGITransport(app=app_for(service))
    await service.start()

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/internal/execution/jobs",
                json={
                    "idempotency_key": "http-run",
                    "domain": "oss",
                    "payload": {"ticket": "INC-77"},
                },
            )
            job_id = created.json()["job"]["job_id"]

            deadline = asyncio.get_running_loop().time() + 1
            while True:
                response = await client.get(f"/internal/execution/jobs/{job_id}")
                body = response.json()
                if body["status"] == JobStatus.SUCCEEDED.value:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise AssertionError("durable HTTP job did not complete")
                await asyncio.sleep(0.01)

            assert body["result"] == {"handled": "INC-77"}
            health = await client.get("/internal/execution/health")
            assert health.json() == {"running": True, "state": "running"}
    finally:
        await service.stop(graceful_timeout_seconds=0.2)


@pytest.mark.asyncio
async def test_cancel_running_job_prevents_result_commit() -> None:
    store = InMemoryDurableJobStore()
    started = asyncio.Event()
    release = asyncio.Event()

    async def handler(job):
        started.set()
        await release.wait()
        return {"unsafe": True}

    worker = DurableWorker(store=store, worker_id="cancel-worker", handlers={"oss": handler})
    pool = DurableWorkerPool(
        store=store,
        workers=[worker],
        policy=DurableWorkerPoolPolicy(idle_poll_seconds=0.005, recovery_interval_seconds=0.01),
    )
    service = DurableExecutionService(store=store, pool=pool)
    transport = ASGITransport(app=app_for(service))
    await service.start()

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/internal/execution/jobs",
                json={"idempotency_key": "cancel-live", "domain": "oss", "payload": {}},
            )
            job_id = created.json()["job"]["job_id"]
            await asyncio.wait_for(started.wait(), timeout=1)

            cancelled = await client.post(f"/internal/execution/jobs/{job_id}/cancel")
            assert cancelled.status_code == 200
            assert cancelled.json()["cancel_requested"] is True
            release.set()

            deadline = asyncio.get_running_loop().time() + 1
            while True:
                final = (await client.get(f"/internal/execution/jobs/{job_id}")).json()
                if final["status"] == JobStatus.CANCELLED.value:
                    break
                if asyncio.get_running_loop().time() >= deadline:
                    raise AssertionError("cancelled durable job did not become terminal")
                await asyncio.sleep(0.01)

            assert final["result"] is None
    finally:
        release.set()
        await service.stop(graceful_timeout_seconds=0.2)
