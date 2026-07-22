from __future__ import annotations

import argparse
import asyncio
import json

from processual_api.auth.delivery_runtime import build_delivery_runtime
from processual_api.db.session import close_db, init_db


async def run_once() -> dict[str, int]:
    await init_db()
    try:
        result = await build_delivery_runtime().dispatcher.dispatch_once()
        return {
            "claimed": result.claimed,
            "delivered": result.delivered,
            "retry_scheduled": result.retry_scheduled,
            "dead_lettered": result.dead_lettered,
            "stale_finalization": result.stale_finalization,
        }
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch authentication delivery outbox rows.")
    parser.add_argument("--once", action="store_true", help="Process one bounded batch and exit.")
    args = parser.parse_args()
    if not args.once:
        parser.error("Only the bounded --once mode is supported.")
    print(json.dumps(asyncio.run(run_once()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "run_once"]
