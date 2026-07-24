from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from processual_api.auth.delivery_runtime import (
    DeliveryRuntime,
    build_delivery_runtime,
)
from processual_api.db.session import close_db, init_db

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeliveryWorkerResult:
    batches: int = 0
    claimed: int = 0
    delivered: int = 0
    retry_scheduled: int = 0
    dead_lettered: int = 0
    stale_finalization: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "batches": self.batches,
            "claimed": self.claimed,
            "delivered": self.delivered,
            "retry_scheduled": self.retry_scheduled,
            "dead_lettered": self.dead_lettered,
            "stale_finalization": self.stale_finalization,
        }


async def run_once() -> dict[str, int]:
    await init_db()

    try:
        result = (
            await build_delivery_runtime()
            .dispatcher
            .dispatch_once()
        )

        return {
            "claimed": result.claimed,
            "delivered": result.delivered,
            "retry_scheduled": result.retry_scheduled,
            "dead_lettered": result.dead_lettered,
            "stale_finalization": result.stale_finalization,
        }
    finally:
        await close_db()


async def run_loop(
    *,
    stop_event: asyncio.Event,
    poll_interval_seconds: float = 1.0,
    runtime_factory: Callable[
        [],
        DeliveryRuntime,
    ] = build_delivery_runtime,
) -> DeliveryWorkerResult:
    if (
        poll_interval_seconds < 0.05
        or poll_interval_seconds > 60
    ):
        raise ValueError(
            "Delivery worker poll interval "
            "is outside its safe range."
        )

    await init_db()

    batches = 0
    claimed = 0
    delivered = 0
    retry_scheduled = 0
    dead_lettered = 0
    stale_finalization = 0

    try:
        runtime = runtime_factory()

        logger.info(
            "identity_delivery_worker_started",
            extra={
                "poll_interval_seconds": (
                    poll_interval_seconds
                ),
            },
        )

        while not stop_event.is_set():
            result = await runtime.dispatcher.dispatch_once()

            batches += 1
            claimed += result.claimed
            delivered += result.delivered
            retry_scheduled += result.retry_scheduled
            dead_lettered += result.dead_lettered
            stale_finalization += result.stale_finalization

            logger.info(
                "identity_delivery_worker_batch_completed",
                extra={
                    "batch_number": batches,
                    "batch_claimed": result.claimed,
                    "batch_delivered": result.delivered,
                    "batch_retry_scheduled": (
                        result.retry_scheduled
                    ),
                    "batch_dead_lettered": (
                        result.dead_lettered
                    ),
                    "batch_stale_finalization": (
                        result.stale_finalization
                    ),
                    "total_claimed": claimed,
                    "total_delivered": delivered,
                    "total_retry_scheduled": (
                        retry_scheduled
                    ),
                    "total_dead_lettered": (
                        dead_lettered
                    ),
                    "total_stale_finalization": (
                        stale_finalization
                    ),
                },
            )

            if stop_event.is_set():
                break

            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=poll_interval_seconds,
                )
            except TimeoutError:
                pass
    except Exception as exc:
        logger.error(
            "identity_delivery_worker_failed",
            extra={
                "exception_type": type(exc).__name__,
                "completed_batches": batches,
            },
        )
        raise
    finally:
        await close_db()

        logger.info(
            "identity_delivery_worker_stopped",
            extra={
                "completed_batches": batches,
                "total_claimed": claimed,
                "total_delivered": delivered,
                "total_retry_scheduled": (
                    retry_scheduled
                ),
                "total_dead_lettered": (
                    dead_lettered
                ),
                "total_stale_finalization": (
                    stale_finalization
                ),
            },
        )

    return DeliveryWorkerResult(
        batches=batches,
        claimed=claimed,
        delivered=delivered,
        retry_scheduled=retry_scheduled,
        dead_lettered=dead_lettered,
        stale_finalization=stale_finalization,
    )


async def run_continuous(
    *,
    poll_interval_seconds: float = 1.0,
    runtime_factory: Callable[
        [],
        DeliveryRuntime,
    ] = build_delivery_runtime,
) -> DeliveryWorkerResult:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    previous_handlers = {
        signum: signal.getsignal(signum)
        for signum in (
            signal.SIGINT,
            signal.SIGTERM,
        )
    }

    def request_stop(
        signum,
        frame,
    ) -> None:
        del signum, frame
        loop.call_soon_threadsafe(stop_event.set)

    try:
        for signum in previous_handlers:
            signal.signal(
                signum,
                request_stop,
            )

        return await run_loop(
            stop_event=stop_event,
            poll_interval_seconds=(
                poll_interval_seconds
            ),
            runtime_factory=runtime_factory,
        )
    finally:
        for signum, previous_handler in (
            previous_handlers.items()
        ):
            signal.signal(
                signum,
                previous_handler,
            )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dispatch authentication delivery "
            "outbox rows."
        )
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--once",
        action="store_true",
        help="Process one bounded batch and exit.",
    )

    mode.add_argument(
        "--continuous",
        action="store_true",
        help=(
            "Run continuously until an operating "
            "system shutdown signal is received."
        ),
    )

    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=1.0,
        help=(
            "Continuous-mode delay between "
            "bounded delivery batches."
        ),
    )

    args = parser.parse_args(argv)

    if args.once:
        payload = asyncio.run(run_once())
    else:
        payload = asyncio.run(
            run_continuous(
                poll_interval_seconds=(
                    args.poll_interval_seconds
                ),
            )
        ).as_dict()

    print(
        json.dumps(
            payload,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DeliveryWorkerResult",
    "main",
    "run_continuous",
    "run_loop",
    "run_once",
]
