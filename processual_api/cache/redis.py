from __future__ import annotations

from ..settings import settings

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

_pool: aioredis.Redis | None = None


def _get_redis_url() -> str:
    return settings.redis_url or ""


async def init_redis():
    global _pool
    url = _get_redis_url()
    if not url or aioredis is None:
        return
    _pool = aioredis.from_url(url, decode_responses=True)


async def close_redis():
    global _pool
    if _pool:
        await _pool.aclose()
    _pool = None


async def get_redis() -> aioredis.Redis | None:
    return _pool


async def check_redis_connection() -> bool:
    if not settings.redis_url or _pool is None:
        return False
    try:
        await _pool.ping()
        return True
    except Exception:
        return False


def rate_limit_key(identifier: str, route: str) -> str:
    return f"{settings.redis_rate_limit_prefix}{identifier}:{route}"
