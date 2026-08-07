from __future__ import annotations

import asyncio
import os

import redis.asyncio as redis


async def main() -> None:
    client = redis.from_url(os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))
    try:
        await client.flushdb()
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
