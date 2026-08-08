"""Protected HTTP control surface for durable execution.

The router is deliberately factory-built and requires an authorization dependency.
It is not mounted by application startup in this module and has no unauthenticated
default. Callers must make an explicit security decision before exposing it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .durable import (
    ExecutionJob,
    ExecutionPriority,
    IdempotencyConflictError,
    JobNotFoundError,
    JobSpec,
    RetryPolicy,
)
from .service import DurableExecutionService


class DurableJobSubmitRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=256)
    domain: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    max_attempts: int = Field(default=3, ge=1, le=20)
    initial_backoff_seconds: float = Field(default=1.0, ge=0, le=3600)
    max_backoff_seconds: float = Field(default=30.0, ge=0, le=86400)
    deadline_at: float | None = None


class DurableJobResponse(BaseModel):
    job_id: str
    idempotency_key: str
    domain: str
    priority: ExecutionPriority
    status: str
    attempt: int
    created_at: float
    updated_at: float
    available_at: float
    cancel_requested: bool
    last_error: str | None
    result: Any = None


class DurableSubmitResponse(BaseModel):
    created: bool
    job: DurableJobResponse


class DurableHealthResponse(BaseModel):
    running: bool
    state: str


def _job_response(job: ExecutionJob) -> DurableJobResponse:
    return DurableJobResponse(
        job_id=job.job_id,
        idempotency_key=job.spec.idempotency_key,
        domain=job.spec.domain,
        priority=job.spec.priority,
        status=job.status.value,
        attempt=job.attempt,
        created_at=job.created_at,
        updated_at=job.updated_at,
        available_at=job.available_at,
        cancel_requested=job.cancel_requested,
        last_error=job.last_error,
        result=job.result,
    )


def create_durable_execution_router(
    *,
    service: DurableExecutionService,
    authorize: Callable[..., Any],
) -> APIRouter:
    """Build the internal control router behind an explicit auth dependency."""

    if authorize is None:
        raise ValueError("durable execution HTTP router requires authorization")

    router = APIRouter(
        prefix="/internal/execution",
        tags=["internal-execution"],
        dependencies=[Depends(authorize)],
    )

    @router.post("/jobs", response_model=DurableSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
    async def submit_job(body: DurableJobSubmitRequest) -> DurableSubmitResponse:
        try:
            retry = RetryPolicy(
                max_attempts=body.max_attempts,
                initial_backoff_seconds=body.initial_backoff_seconds,
                max_backoff_seconds=body.max_backoff_seconds,
            )
            submitted = await service.submit(
                JobSpec(
                    idempotency_key=body.idempotency_key,
                    domain=body.domain,
                    payload=body.payload,
                    priority=body.priority,
                    retry=retry,
                    deadline_at=body.deadline_at,
                )
            )
        except IdempotencyConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="idempotency key conflicts with an existing durable job",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        return DurableSubmitResponse(created=submitted.created, job=_job_response(submitted.job))

    @router.get("/jobs/{job_id}", response_model=DurableJobResponse)
    async def get_job(job_id: str) -> DurableJobResponse:
        try:
            return _job_response(await service.status(job_id))
        except JobNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="durable job not found") from exc

    @router.post("/jobs/{job_id}/cancel", response_model=DurableJobResponse)
    async def cancel_job(job_id: str) -> DurableJobResponse:
        try:
            return _job_response(await service.cancel(job_id))
        except JobNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="durable job not found") from exc

    @router.get("/health", response_model=DurableHealthResponse)
    async def execution_health() -> DurableHealthResponse:
        health = service.health()
        return DurableHealthResponse(running=health.running, state=health.state)

    return router
