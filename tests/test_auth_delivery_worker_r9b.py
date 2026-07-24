from __future__ import annotations

import asyncio
import json
import logging
import signal
from types import SimpleNamespace

import pytest

import processual_api.auth.delivery_worker as worker_module
from processual_api.auth.delivery_worker import (
    DeliveryWorkerResult,
    main,
    run_continuous,
    run_loop,
)


class SequencedDispatcher:
    def __init__(
        self,
        *,
        stop_event,
        results,
    ) -> None:
        self.stop_event = stop_event
        self.results = list(results)
        self.calls = 0

    async def dispatch_once(self):
        if not self.results:
            raise AssertionError(
                "Worker dispatched more batches than expected."
            )

        self.calls += 1
        result = self.results.pop(0)

        if not self.results:
            self.stop_event.set()

        return result


def _result(
    *,
    claimed=0,
    delivered=0,
    retry_scheduled=0,
    dead_lettered=0,
    stale_finalization=0,
):
    return SimpleNamespace(
        claimed=claimed,
        delivered=delivered,
        retry_scheduled=retry_scheduled,
        dead_lettered=dead_lettered,
        stale_finalization=stale_finalization,
    )


def test_worker_loop_accumulates_batches_and_closes_database(
    monkeypatch,
):
    lifecycle = []

    async def fake_init_db():
        lifecycle.append("init")

    async def fake_close_db():
        lifecycle.append("close")

    monkeypatch.setattr(
        worker_module,
        "init_db",
        fake_init_db,
    )

    monkeypatch.setattr(
        worker_module,
        "close_db",
        fake_close_db,
    )

    stop_event = asyncio.Event()

    dispatcher = SequencedDispatcher(
        stop_event=stop_event,
        results=[
            _result(
                claimed=2,
                delivered=1,
                retry_scheduled=1,
            ),
            _result(
                claimed=3,
                delivered=2,
                dead_lettered=1,
                stale_finalization=1,
            ),
        ],
    )

    result = asyncio.run(
        run_loop(
            stop_event=stop_event,
            poll_interval_seconds=0.05,
            runtime_factory=lambda: SimpleNamespace(
                dispatcher=dispatcher
            ),
        )
    )

    assert result == DeliveryWorkerResult(
        batches=2,
        claimed=5,
        delivered=3,
        retry_scheduled=1,
        dead_lettered=1,
        stale_finalization=1,
    )

    assert result.as_dict() == {
        "batches": 2,
        "claimed": 5,
        "delivered": 3,
        "retry_scheduled": 1,
        "dead_lettered": 1,
        "stale_finalization": 1,
    }

    assert dispatcher.calls == 2
    assert lifecycle == [
        "init",
        "close",
    ]


def test_worker_loop_closes_database_when_dispatch_fails(
    monkeypatch,
):
    lifecycle = []

    async def fake_init_db():
        lifecycle.append("init")

    async def fake_close_db():
        lifecycle.append("close")

    class FailingDispatcher:
        async def dispatch_once(self):
            raise RuntimeError(
                "database connection failed"
            )

    monkeypatch.setattr(
        worker_module,
        "init_db",
        fake_init_db,
    )

    monkeypatch.setattr(
        worker_module,
        "close_db",
        fake_close_db,
    )

    with pytest.raises(
        RuntimeError,
        match="database connection failed",
    ):
        asyncio.run(
            run_loop(
                stop_event=asyncio.Event(),
                poll_interval_seconds=0.05,
                runtime_factory=lambda: SimpleNamespace(
                    dispatcher=FailingDispatcher()
                ),
            )
        )

    assert lifecycle == [
        "init",
        "close",
    ]


def test_worker_loop_does_not_dispatch_when_already_stopped(
    monkeypatch,
):
    lifecycle = []

    async def fake_init_db():
        lifecycle.append("init")

    async def fake_close_db():
        lifecycle.append("close")

    class ForbiddenDispatcher:
        async def dispatch_once(self):
            raise AssertionError(
                "Stopped worker must not dispatch."
            )

    monkeypatch.setattr(
        worker_module,
        "init_db",
        fake_init_db,
    )

    monkeypatch.setattr(
        worker_module,
        "close_db",
        fake_close_db,
    )

    stop_event = asyncio.Event()
    stop_event.set()

    result = asyncio.run(
        run_loop(
            stop_event=stop_event,
            poll_interval_seconds=0.05,
            runtime_factory=lambda: SimpleNamespace(
                dispatcher=ForbiddenDispatcher()
            ),
        )
    )

    assert result == DeliveryWorkerResult()
    assert lifecycle == [
        "init",
        "close",
    ]


@pytest.mark.parametrize(
    "poll_interval_seconds",
    (
        0,
        0.01,
        60.01,
        120,
    ),
)
def test_worker_loop_rejects_unsafe_poll_interval(
    poll_interval_seconds,
):
    with pytest.raises(
        ValueError,
        match="poll interval",
    ):
        asyncio.run(
            run_loop(
                stop_event=asyncio.Event(),
                poll_interval_seconds=(
                    poll_interval_seconds
                ),
            )
        )


def test_run_continuous_installs_and_restores_signal_handlers(
    monkeypatch,
):
    installed_handlers = {}
    restored_handlers = []

    previous_handlers = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }

    def fake_getsignal(signum):
        return previous_handlers[signum]

    def fake_signal(
        signum,
        handler,
    ):
        if handler is previous_handlers[signum]:
            restored_handlers.append(signum)
        else:
            installed_handlers[signum] = handler

    async def fake_run_loop(
        *,
        stop_event,
        poll_interval_seconds,
        runtime_factory,
    ):
        assert poll_interval_seconds == 2.5
        assert runtime_factory() == "runtime"
        assert stop_event.is_set() is False

        installed_handlers[signal.SIGTERM](
            signal.SIGTERM,
            None,
        )

        await asyncio.sleep(0)

        assert stop_event.is_set() is True

        return DeliveryWorkerResult(
            batches=3,
            claimed=4,
            delivered=2,
            retry_scheduled=1,
            dead_lettered=1,
        )

    monkeypatch.setattr(
        worker_module.signal,
        "getsignal",
        fake_getsignal,
    )

    monkeypatch.setattr(
        worker_module.signal,
        "signal",
        fake_signal,
    )

    monkeypatch.setattr(
        worker_module,
        "run_loop",
        fake_run_loop,
    )

    result = asyncio.run(
        run_continuous(
            poll_interval_seconds=2.5,
            runtime_factory=lambda: "runtime",
        )
    )

    assert result == DeliveryWorkerResult(
        batches=3,
        claimed=4,
        delivered=2,
        retry_scheduled=1,
        dead_lettered=1,
    )

    assert restored_handlers == [
        signal.SIGINT,
        signal.SIGTERM,
    ]


def test_run_continuous_restores_handlers_on_failure(
    monkeypatch,
):
    previous_handlers = {
        signal.SIGINT: object(),
        signal.SIGTERM: object(),
    }

    restored_handlers = []

    def fake_getsignal(signum):
        return previous_handlers[signum]

    def fake_signal(
        signum,
        handler,
    ):
        if handler is previous_handlers[signum]:
            restored_handlers.append(signum)

    async def failing_run_loop(**values):
        del values
        raise RuntimeError("worker failed")

    monkeypatch.setattr(
        worker_module.signal,
        "getsignal",
        fake_getsignal,
    )

    monkeypatch.setattr(
        worker_module.signal,
        "signal",
        fake_signal,
    )

    monkeypatch.setattr(
        worker_module,
        "run_loop",
        failing_run_loop,
    )

    with pytest.raises(
        RuntimeError,
        match="worker failed",
    ):
        asyncio.run(
            run_continuous(
                runtime_factory=lambda: "runtime",
            )
        )

    assert restored_handlers == [
        signal.SIGINT,
        signal.SIGTERM,
    ]


def test_main_continuous_mode_prints_aggregate(
    monkeypatch,
    capsys,
):
    observed_intervals = []

    async def fake_run_continuous(
        *,
        poll_interval_seconds,
        runtime_factory=worker_module.build_delivery_runtime,
    ):
        del runtime_factory

        observed_intervals.append(
            poll_interval_seconds
        )

        return DeliveryWorkerResult(
            batches=2,
            claimed=5,
            delivered=3,
            retry_scheduled=1,
            dead_lettered=1,
        )

    monkeypatch.setattr(
        worker_module,
        "run_continuous",
        fake_run_continuous,
    )

    exit_code = main(
        [
            "--continuous",
            "--poll-interval-seconds",
            "2.5",
        ]
    )

    assert exit_code == 0
    assert observed_intervals == [2.5]

    assert json.loads(
        capsys.readouterr().out
    ) == {
        "batches": 2,
        "claimed": 5,
        "dead_lettered": 1,
        "delivered": 3,
        "retry_scheduled": 1,
        "stale_finalization": 0,
    }


def test_main_once_mode_remains_supported(
    monkeypatch,
    capsys,
):
    async def fake_run_once():
        return {
            "claimed": 1,
            "delivered": 1,
            "retry_scheduled": 0,
            "dead_lettered": 0,
            "stale_finalization": 0,
        }

    monkeypatch.setattr(
        worker_module,
        "run_once",
        fake_run_once,
    )

    assert main(["--once"]) == 0

    assert json.loads(
        capsys.readouterr().out
    ) == {
        "claimed": 1,
        "dead_lettered": 0,
        "delivered": 1,
        "retry_scheduled": 0,
        "stale_finalization": 0,
    }


@pytest.mark.parametrize(
    "arguments",
    (
        (),
        (
            "--once",
            "--continuous",
        ),
    ),
)
def test_main_requires_exactly_one_mode(
    arguments,
):
    with pytest.raises(SystemExit) as captured:
        main(list(arguments))

    assert captured.value.code == 2


def test_worker_emits_structured_operational_heartbeat(
    monkeypatch,
    caplog,
):
    async def fake_init_db():
        return None

    async def fake_close_db():
        return None

    monkeypatch.setattr(
        worker_module,
        "init_db",
        fake_init_db,
    )

    monkeypatch.setattr(
        worker_module,
        "close_db",
        fake_close_db,
    )

    stop_event = asyncio.Event()

    dispatcher = SequencedDispatcher(
        stop_event=stop_event,
        results=[
            _result(),
            _result(
                claimed=2,
                delivered=1,
                retry_scheduled=1,
            ),
        ],
    )

    caplog.set_level(
        logging.INFO,
        logger=worker_module.__name__,
    )

    result = asyncio.run(
        run_loop(
            stop_event=stop_event,
            poll_interval_seconds=0.05,
            runtime_factory=lambda: SimpleNamespace(
                dispatcher=dispatcher
            ),
        )
    )

    assert result == DeliveryWorkerResult(
        batches=2,
        claimed=2,
        delivered=1,
        retry_scheduled=1,
    )

    started = [
        record
        for record in caplog.records
        if record.getMessage()
        == "identity_delivery_worker_started"
    ]

    batches = [
        record
        for record in caplog.records
        if record.getMessage()
        == "identity_delivery_worker_batch_completed"
    ]

    stopped = [
        record
        for record in caplog.records
        if record.getMessage()
        == "identity_delivery_worker_stopped"
    ]

    assert len(started) == 1
    assert started[0].poll_interval_seconds == 0.05

    assert len(batches) == 2

    assert batches[0].batch_number == 1
    assert batches[0].batch_claimed == 0
    assert batches[0].total_claimed == 0

    assert batches[1].batch_number == 2
    assert batches[1].batch_claimed == 2
    assert batches[1].batch_delivered == 1
    assert batches[1].batch_retry_scheduled == 1
    assert batches[1].total_claimed == 2
    assert batches[1].total_delivered == 1

    assert len(stopped) == 1
    assert stopped[0].completed_batches == 2
    assert stopped[0].total_claimed == 2
    assert stopped[0].total_delivered == 1


def test_worker_failure_log_does_not_expose_exception_message(
    monkeypatch,
    caplog,
):
    sensitive_email = "".join(
        (
            "private",
            "@example.invalid",
        )
    )

    sensitive_token = "-".join(
        (
            "super",
            "secret",
            "action",
            "token",
        )
    )

    sensitive_text = (
        f"recipient={sensitive_email} "
        f"token={sensitive_token}"
    )

    async def fake_init_db():
        return None

    async def fake_close_db():
        return None

    class FailingDispatcher:
        async def dispatch_once(self):
            raise RuntimeError(sensitive_text)

    monkeypatch.setattr(
        worker_module,
        "init_db",
        fake_init_db,
    )

    monkeypatch.setattr(
        worker_module,
        "close_db",
        fake_close_db,
    )

    caplog.set_level(
        logging.INFO,
        logger=worker_module.__name__,
    )

    with pytest.raises(
        RuntimeError,
        match=sensitive_token,
    ):
        asyncio.run(
            run_loop(
                stop_event=asyncio.Event(),
                poll_interval_seconds=0.05,
                runtime_factory=lambda: SimpleNamespace(
                    dispatcher=FailingDispatcher()
                ),
            )
        )

    failures = [
        record
        for record in caplog.records
        if record.getMessage()
        == "identity_delivery_worker_failed"
    ]

    stopped = [
        record
        for record in caplog.records
        if record.getMessage()
        == "identity_delivery_worker_stopped"
    ]

    assert len(failures) == 1
    assert failures[0].exception_type == "RuntimeError"
    assert failures[0].completed_batches == 0

    assert len(stopped) == 1
    assert stopped[0].completed_batches == 0

    log_text = caplog.text

    assert sensitive_email not in log_text
    assert sensitive_token not in log_text
