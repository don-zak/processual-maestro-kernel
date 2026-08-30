"""Health check endpoints — liveness and readiness probes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from cgtlib._backend import HAS_PRIVATE_COMPUTE as _CGT_PRIVATE

from ..readiness import check_adapter_config_integrity
from ..settings import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def health_live():
    return {"status": "alive", "service": "processual-maestro-kernel", "version": "2.0.0"}


@router.get("/ready")
async def health_ready():
    deps = {
        "cgtlib": _CGT_PRIVATE,
        "processual_kernel": True,
        "cryptography": True,
    }

    db_ok = False
    if settings.database_url:
        try:
            from ..db.session import check_db_connection

            db_ok = await check_db_connection()
        except Exception:
            db_ok = False
    deps["database"] = db_ok

    redis_ok = False
    if settings.redis_url:
        try:
            from ..cache.redis import check_redis_connection

            redis_ok = await check_redis_connection()
        except Exception:
            redis_ok = False
    deps["redis"] = redis_ok

    adapter_config_path = Path(__file__).resolve().parent.parent / "data" / "adapter_config.json"
    adapter_config = check_adapter_config_integrity(adapter_config_path)
    deps["adapter_config"] = adapter_config.ok

    all_ok = all(deps.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "dependencies": deps,
        "readiness": {
            "adapter_config": {
                "status": adapter_config.status,
                "detail": adapter_config.detail,
            }
        },
    }