"""Telemetry ingestion and query routes — persisted to JSONL."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..auth.security import get_current_user
from ..cgt_governor.data.telemetry_storage import telemetry_store
from ..cgt_governor.security import sign_response

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryPoint(BaseModel):
    metric: str
    value: float
    labels: dict[str, str] = {}


class TelemetryBatch(BaseModel):
    points: list[TelemetryPoint]


@router.post("/ingest")
async def ingest_telemetry(
    batch: TelemetryBatch,
    current_user: dict = Depends(get_current_user),
):
    for point in batch.points:
        telemetry_store.ingest(point.metric, point.value, point.labels)
    try:
        from processual_kernel.observability.metrics import increment_telemetry_ingested
        increment_telemetry_ingested(len(batch.points))
    except ImportError:
        pass
    return {"ingested": len(batch.points), "status": "ok"}


@router.get("/query")
async def query_telemetry(
    metric: str | None = Query(None, description="Filter by metric name"),
    since: str | None = Query(None, description="ISO timestamp filter (entries >= this)"),
    limit: int = Query(100, description="Max results"),
    current_user: dict = Depends(get_current_user),
):
    entries = telemetry_store.query(metric=metric, since=since, limit=limit)
    sig = sign_response({"telemetry_query": True, "metric": metric, "count": len(entries)})
    return {
        "total": len(entries),
        "entries": entries,
        "signature": sig,
    }
