"""Explicit Redis durable-store activation helpers.

The optimized store remains opt-in. Importing this module does not construct a
Redis client or change application startup defaults; callers must pass an
initialized client and explicitly request the optimized implementation.
"""

from __future__ import annotations

from typing import Any

from .redis_store import RedisDurableJobStore
from .redis_store_optimized import OptimizedRedisDurableJobStore


def build_redis_durable_store(
    redis_client: Any,
    *,
    prefix: str = "maestro:durable",
    optimized: bool = False,
) -> RedisDurableJobStore:
    """Build the safe Redis store unless optimized execution is explicitly enabled."""

    store_type = OptimizedRedisDurableJobStore if optimized else RedisDurableJobStore
    return store_type(redis_client, prefix=prefix)
