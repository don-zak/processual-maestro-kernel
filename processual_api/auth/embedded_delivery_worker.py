from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from processual_api.auth.delivery_runtime import DeliveryRuntime, build_delivery_runtime

# Route lifecycle records through Uvicorn's operational logger so INFO-level
# worker evidence is visible in hosted service logs without serializing
# provider/customer payloads. Safe aggregate counters are embedded in the
# message because hosted text formatters may discard LogRecord.extra fields.
logger = logging.getLogger("uvicorn.error")

_ENABLED_VALUES = frozenset({"1", "true", "yes", "on"})
_DEFAULT_POLL_INTERVAL_SECONDS = 1.0
_MIN_POLL_INTERVAL_SECONDS = 0.05
_MAX_POLL_INTERVAL_SECONDS = 60.0
_SHUTDOWN_GRACE_SECONDS = 5.0


def embedded_delivery_worker_enabled(environ: dict[str, str] | None = None) -> bool:
    values = os.environ if environ is None else environ
    return values.get("AUTH_DELIVERY_EMBEDDED_WORKER_ENABLED", "false").strip().casefold() in _ENABLED_VALUES


def embedded_delivery_worker_poll_interval(environ: dict[str, str] | None = None) -> float:
    values = os.environ if environ is None else environ
    raw_value = values.get(
        "AUTH_DELIVERY_EMBEDDED_WORKER_POLL_INTERVAL_SECONDS",
        str(_DEFAULT_POLL_INTERVAL_SECONDS),
    )
    try:
        interval = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Embedded delivery worker poll interval is invalid.") from exc
    if interval < _MIN_POLL_INTERVAL_SECONDS or interval > _MAX_POLL_INTERVAL_SECONDS:
        raise ValueError("Embedded delivery worker poll interval is outside its safe range.")
    return interval


async def run_embedded_delivery_loop(
    *,
    stop_event: asyncio.Event,
    poll_interval_seconds: float,
    runtime_factory: Callable[[], DeliveryRuntime] = build_delivery_runtime,
) -> None:
    if poll_interval_seconds < _MIN_POLL_INTERVAL_SECONDS or poll_interval_seconds > _MAX_POLL_INTERVAL_SECONDS:
        raise ValueError("Embedded delivery worker poll interval is outside its safe range.")

    try:
        runtime = runtime_factory()
    except Exception as exc:
        logger.error(
            "identity_delivery_embedded_worker_runtime_unavailable exception_type=%s",
            type(exc).__name__,
        )
        return

    logger.info(
        "identity_delivery_embedded_worker_started poll_interval_seconds=%s",
        poll_interval_seconds,
    )

    batches = 0
    try:
        while not stop_event.is_set():
            try:
                result = await runtime.dispatcher.dispatch_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    "identity_delivery_embedded_worker_batch_failed exception_type=%s completed_batches=%s",
                    type(exc).__name__,
                    batches,
                )
            else:
                batches += 1
                logger.info(
                    (
                        "identity_delivery_embedded_worker_batch_completed "
                        "batch_number=%s claimed=%s delivered=%s "
                        "retry_scheduled=%s dead_lettered=%s "
                        "stale_finalization=%s"
                    ),
                    batches,
                    result.claimed,
                    result.delivered,
                    result.retry_scheduled,
                    result.dead_lettered,
                    result.stale_finalization,
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
    finally:
        logger.info(
            "identity_delivery_embedded_worker_stopped completed_batches=%s",
            batches,
        )


@asynccontextmanager
async def delivery_router_lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not embedded_delivery_worker_enabled():
        yield
        return

    try:
        poll_interval_seconds = embedded_delivery_worker_poll_interval()
    except ValueError as exc:
        logger.error(
            "identity_delivery_embedded_worker_configuration_invalid exception_type=%s",
            type(exc).__name__,
        )
        yield
        return

    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_embedded_delivery_loop(
            stop_event=stop_event,
            poll_interval_seconds=poll_interval_seconds,
        ),
        name="processual-auth-delivery-embedded-worker",
    )
    app.state.auth_delivery_embedded_worker_task = task

    try:
        yield
    finally:
        stop_event.set()
        try:
            await asyncio.wait_for(task, timeout=_SHUTDOWN_GRACE_SECONDS)
        except TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            logger.warning("identity_delivery_embedded_worker_shutdown_cancelled")
        finally:
            if getattr(app.state, "auth_delivery_embedded_worker_task", None) is task:
                del app.state.auth_delivery_embedded_worker_task


__all__ = [
    "delivery_router_lifespan",
    "embedded_delivery_worker_enabled",
    "embedded_delivery_worker_poll_interval",
    "run_embedded_delivery_loop",
]
