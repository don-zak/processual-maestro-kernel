from __future__ import annotations

import logging
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_kernel.observability import logging as logging_mod
from processual_kernel.observability import metrics as metrics_mod
from processual_kernel.observability import sentry as sentry_mod


def test_log_event_defaults_and_timestamp_shape() -> None:
    event = logging_mod.LogEvent(event_type="checkpoint")
    assert event.workflow_id is None
    assert event.agent_id is None
    assert event.status == "info"
    assert event.latency_ms == 0.0
    assert event.metadata == {}
    assert "T" in event.timestamp


def test_structured_logger_fallback_constructor_and_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_logger = Mock(spec=logging.Logger)
    monkeypatch.setattr(logging_mod, "_structlog_available", False)
    monkeypatch.setattr(logging_mod.logging, "getLogger", Mock(return_value=fake_logger))
    monkeypatch.setattr(logging_mod.logging, "StreamHandler", Mock(return_value=Mock()))

    logger = logging_mod.StructuredLogger("fallback")
    assert logger._logger is fake_logger

    logger.info("evt", key=1)
    logger.warning("warn", value="x")
    logger.error("err", failed=True)

    fake_logger.info.assert_called_once_with("evt {'key': 1}")
    fake_logger.warning.assert_called_once_with("warn {'value': 'x'}")
    fake_logger.error.assert_called_once_with("err {'failed': True}")


def test_structured_logger_structlog_constructor_and_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_logger = Mock()
    configure = Mock()
    get_logger = Mock(return_value=fake_logger)
    fake_structlog = SimpleNamespace(
        configure=configure,
        get_logger=get_logger,
        stdlib=SimpleNamespace(
            filter_by_level=object(),
            add_logger_name=object(),
            add_log_level=object(),
            PositionalArgumentsFormatter=lambda: "positional",
        ),
        processors=SimpleNamespace(
            TimeStamper=lambda fmt: ("time", fmt),
            JSONRenderer=lambda: "json",
        ),
        PrintLoggerFactory=lambda: "factory",
    )
    monkeypatch.setattr(logging_mod, "_structlog_available", True)
    monkeypatch.setattr(logging_mod, "structlog", fake_structlog, raising=False)

    logger = logging_mod.StructuredLogger("structured")
    get_logger.assert_called_once_with("structured")
    assert configure.call_count == 1

    logger.info("evt", a=1)
    logger.warning("warn", b=2)
    logger.error("err", c=3)
    fake_logger.info.assert_called_once_with("evt", a=1)
    fake_logger.warning.assert_called_once_with("warn", b=2)
    fake_logger.error.assert_called_once_with("err", c=3)


def test_log_event_merges_metadata_and_delegates() -> None:
    logger = logging_mod.StructuredLogger.__new__(logging_mod.StructuredLogger)
    logger.info = Mock()
    event = logging_mod.LogEvent(
        event_type="handoff",
        workflow_id="wf-1",
        agent_id="agent-1",
        fate_rank="A",
        operation="transfer",
        status="ok",
        latency_ms=12.5,
        metadata={"custom": 7, "status": "override"},
        timestamp="2026-08-12T00:00:00+00:00",
    )

    logger.log_event(event)

    logger.info.assert_called_once_with(
        "handoff",
        event_type="handoff",
        workflow_id="wf-1",
        agent_id="agent-1",
        fate_rank="A",
        operation="transfer",
        status="override",
        latency_ms=12.5,
        timestamp="2026-08-12T00:00:00+00:00",
        custom=7,
    )


def test_get_logger_caches_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = object()
    constructor = Mock(return_value=fake)
    monkeypatch.setattr(logging_mod, "StructuredLogger", constructor)
    logging_mod._loggers.clear()

    first = logging_mod.get_logger("cached")
    second = logging_mod.get_logger("cached")
    third = logging_mod.get_logger("other")

    assert first is second is fake
    assert third is fake
    assert constructor.call_count == 2


class _Counter:
    def __init__(self) -> None:
        self.labels_calls: list[dict[str, object]] = []
        self.inc_calls: list[float] = []

    def labels(self, **kwargs: object) -> _Counter:
        self.labels_calls.append(kwargs)
        return self

    def inc(self, amount: float = 1.0) -> None:
        self.inc_calls.append(amount)


class _Histogram:
    def __init__(self) -> None:
        self.values: list[float] = []

    def observe(self, amount: float) -> None:
        self.values.append(amount)


def test_metrics_wrappers_delegate_to_expected_collectors(monkeypatch: pytest.MonkeyPatch) -> None:
    cgt = _Counter()
    fate = _Counter()
    checkpoints = _Counter()
    governance = _Counter()
    discord = _Counter()
    crypto_ops = _Counter()
    crypto_failures = _Counter()
    latency = _Histogram()
    pdf = _Counter()
    simulations = _Counter()
    telemetry = _Counter()

    monkeypatch.setattr(metrics_mod, "CGTEvaluationsCounter", cgt)
    monkeypatch.setattr(metrics_mod, "FateRankCounter", fate)
    monkeypatch.setattr(metrics_mod, "WorkflowCheckpointsCounter", checkpoints)
    monkeypatch.setattr(metrics_mod, "GovernanceActionsCounter", governance)
    monkeypatch.setattr(metrics_mod, "DiscordAlertsCounter", discord)
    monkeypatch.setattr(metrics_mod, "CryptoOperationsCounter", crypto_ops)
    monkeypatch.setattr(metrics_mod, "CryptoFailuresCounter", crypto_failures)
    monkeypatch.setattr(metrics_mod, "WorkflowLatencyHistogram", latency)
    monkeypatch.setattr(metrics_mod, "PDFReportsCounter", pdf)
    monkeypatch.setattr(metrics_mod, "SimulationRunsCounter", simulations)
    monkeypatch.setattr(metrics_mod, "TelemetryIngestedCounter", telemetry)

    metrics_mod.increment_cgt_evaluations()
    metrics_mod.increment_fate_rank("A")
    metrics_mod.increment_workflow_checkpoint()
    metrics_mod.increment_governance_action("reroute")
    metrics_mod.increment_discord_alert()
    metrics_mod.increment_crypto_operation()
    metrics_mod.increment_crypto_operation("ChaCha20")
    metrics_mod.increment_crypto_failure()
    metrics_mod.observe_workflow_latency(1.25)
    metrics_mod.increment_pdf_report()
    metrics_mod.increment_pdf_report("audit")
    metrics_mod.increment_simulation_run()
    metrics_mod.increment_simulation_run("agent-7")
    metrics_mod.increment_telemetry_ingested()
    metrics_mod.increment_telemetry_ingested(4)

    assert cgt.inc_calls == [1.0]
    assert fate.labels_calls == [{"rank": "A"}]
    assert fate.inc_calls == [1.0]
    assert checkpoints.inc_calls == [1.0]
    assert governance.labels_calls == [{"action": "reroute"}]
    assert discord.inc_calls == [1.0]
    assert crypto_ops.labels_calls == [{"algorithm": "AES-256-GCM"}, {"algorithm": "ChaCha20"}]
    assert crypto_ops.inc_calls == [1.0, 1.0]
    assert crypto_failures.inc_calls == [1.0]
    assert latency.values == [1.25]
    assert pdf.labels_calls == [{"type": "governance"}, {"type": "audit"}]
    assert simulations.labels_calls == [{"agent_id": "unknown"}, {"agent_id": "agent-7"}]
    assert telemetry.inc_calls == [1.0, 4]


def test_noop_metric_collectors_accept_labels_increment_and_observe() -> None:
    counter = metrics_mod._NoopCounter() if hasattr(metrics_mod, "_NoopCounter") else None
    histogram = metrics_mod._NoopHistogram() if hasattr(metrics_mod, "_NoopHistogram") else None
    if counter is None or histogram is None:
        pytest.skip("prometheus fallback classes are defined only when prometheus_client import fails")

    assert counter.labels(rank="A") is counter
    assert counter.inc() is None
    assert counter.inc(3.0) is None
    assert histogram.observe(2.5) is None


def _fake_sentry_sdk() -> tuple[SimpleNamespace, Mock, Mock, list[dict[str, object]]]:
    init = Mock()
    capture_exception = Mock()
    capture_message = Mock()
    extras: list[dict[str, object]] = []

    class Scope:
        def __enter__(self) -> Scope:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def set_extra(self, key: str, value: object) -> None:
            extras.append({key: value})

    sdk = SimpleNamespace(
        init=init,
        push_scope=lambda: Scope(),
        capture_exception=capture_exception,
        capture_message=capture_message,
    )
    return sdk, init, capture_exception, capture_message, extras


def test_init_sentry_returns_false_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    sentry_mod.SENTRY_DSN = None
    assert sentry_mod.init_sentry(None) is False
    assert sentry_mod.SENTRY_DSN is None


def test_init_sentry_uses_environment_and_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, init, _, _, _ = _fake_sentry_sdk()
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    monkeypatch.setenv("SENTRY_DSN", "https://example.invalid/123")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    sentry_mod.SENTRY_DSN = None

    assert sentry_mod.init_sentry(environment="test", release="9.9.9") is True
    assert sentry_mod.SENTRY_DSN == "https://example.invalid/123"
    init.assert_called_once_with(
        dsn="https://example.invalid/123",
        environment="test",
        release="9.9.9",
        traces_sample_rate=0.25,
    )


def test_init_sentry_explicit_dsn_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, init, _, _, _ = _fake_sentry_sdk()
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    monkeypatch.setenv("SENTRY_DSN", "env-dsn")
    monkeypatch.delenv("SENTRY_TRACES_SAMPLE_RATE", raising=False)

    assert sentry_mod.init_sentry("explicit-dsn") is True
    init.assert_called_once_with(
        dsn="explicit-dsn",
        environment="development",
        release="2.0.0",
        traces_sample_rate=0.1,
    )


def test_init_sentry_handles_sdk_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, init, _, _, _ = _fake_sentry_sdk()
    init.side_effect = RuntimeError("boom")
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = None

    assert sentry_mod.init_sentry("dsn") is False
    assert sentry_mod.SENTRY_DSN == "dsn"


def test_capture_exception_noops_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, _, capture_exception, _, _ = _fake_sentry_sdk()
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = None

    sentry_mod.capture_exception(ValueError("x"), {"workflow": "wf-1"})
    capture_exception.assert_not_called()


def test_capture_exception_records_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, _, capture_exception, _, extras = _fake_sentry_sdk()
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = "dsn"
    exc = ValueError("bad")

    sentry_mod.capture_exception(exc, {"workflow": "wf-2", "attempt": 3})

    capture_exception.assert_called_once_with(exc)
    assert extras == [{"workflow": "wf-2"}, {"attempt": 3}]


def test_capture_exception_swallows_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, _, capture_exception, _, _ = _fake_sentry_sdk()
    capture_exception.side_effect = RuntimeError("sdk down")
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = "dsn"

    sentry_mod.capture_exception(RuntimeError("app"))
    capture_exception.assert_called_once()


def test_capture_message_noops_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, _, _, capture_message, _ = _fake_sentry_sdk()
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = None

    sentry_mod.capture_message("hello", extra={"x": 1})
    capture_message.assert_not_called()


def test_capture_message_records_level_and_extras(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, _, _, capture_message, extras = _fake_sentry_sdk()
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = "dsn"

    sentry_mod.capture_message("degraded", level="warning", extra={"workflow": "wf-3"})

    capture_message.assert_called_once_with("degraded", level="warning")
    assert extras == [{"workflow": "wf-3"}]


def test_capture_message_swallows_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, _, _, capture_message, _ = _fake_sentry_sdk()
    capture_message.side_effect = RuntimeError("sdk down")
    monkeypatch.setitem(sys.modules, "sentry_sdk", sdk)
    sentry_mod.SENTRY_DSN = "dsn"

    sentry_mod.capture_message("hello")
    capture_message.assert_called_once_with("hello", level="info")
