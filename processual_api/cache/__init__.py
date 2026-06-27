"""Redis cache and rate-limiting backend."""

from .redis import close_redis, init_redis

__all__ = ["init_redis", "close_redis"]
