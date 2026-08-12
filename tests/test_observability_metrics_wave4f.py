from unittest.mock import Mock

import processual_kernel.observability.metrics as metrics


def test_simple_metric_wrappers_delegate_to_counters(monkeypatch) -> None:
    cgt = Mock()
    checkpoints = Mock()
    discord = Mock()
    crypto_failures = Mock()
    telemetry = Mock()

    monkeypatch.setattr(metrics, "CGTEvaluationsCounter", cgt)
    monkeypatch.setattr(metrics, "WorkflowCheckpointsCounter", checkpoints)
    monkeypatch.setattr(metrics, "DiscordAlertsCounter", discord)
    monkeypatch.setattr(metrics, "CryptoFailuresCounter", crypto_failures)
    monkeypatch.setattr(metrics, "TelemetryIngestedCounter", telemetry)

    metrics.increment_cgt_evaluations()
    metrics.increment_workflow_checkpoint()
    metrics.increment_discord_alert()
    metrics.increment_crypto_failure()
    metrics.increment_telemetry_ingested(7)

    cgt.inc.assert_called_once_with()
    checkpoints.inc.assert_called_once_with()
    discord.inc.assert_called_once_with()
    crypto_failures.inc.assert_called_once_with()
    telemetry.inc.assert_called_once_with(7)


def test_labeled_metric_wrappers_apply_expected_labels(monkeypatch) -> None:
    fate = Mock()
    governance = Mock()
    crypto = Mock()
    pdf = Mock()
    simulation = Mock()

    fate_child = Mock()
    governance_child = Mock()
    crypto_child = Mock()
    pdf_child = Mock()
    simulation_child = Mock()

    fate.labels.return_value = fate_child
    governance.labels.return_value = governance_child
    crypto.labels.return_value = crypto_child
    pdf.labels.return_value = pdf_child
    simulation.labels.return_value = simulation_child

    monkeypatch.setattr(metrics, "FateRankCounter", fate)
    monkeypatch.setattr(metrics, "GovernanceActionsCounter", governance)
    monkeypatch.setattr(metrics, "CryptoOperationsCounter", crypto)
    monkeypatch.setattr(metrics, "PDFReportsCounter", pdf)
    monkeypatch.setattr(metrics, "SimulationRunsCounter", simulation)

    metrics.increment_fate_rank("critical")
    metrics.increment_governance_action("pause")
    metrics.increment_crypto_operation()
    metrics.increment_pdf_report()
    metrics.increment_simulation_run()

    fate.labels.assert_called_once_with(rank="critical")
    fate_child.inc.assert_called_once_with()
    governance.labels.assert_called_once_with(action="pause")
    governance_child.inc.assert_called_once_with()
    crypto.labels.assert_called_once_with(algorithm="AES-256-GCM")
    crypto_child.inc.assert_called_once_with()
    pdf.labels.assert_called_once_with(type="governance")
    pdf_child.inc.assert_called_once_with()
    simulation.labels.assert_called_once_with(agent_id="unknown")
    simulation_child.inc.assert_called_once_with()


def test_labeled_metric_wrappers_accept_explicit_values(monkeypatch) -> None:
    crypto = Mock()
    pdf = Mock()
    simulation = Mock()
    crypto.labels.return_value = Mock()
    pdf.labels.return_value = Mock()
    simulation.labels.return_value = Mock()

    monkeypatch.setattr(metrics, "CryptoOperationsCounter", crypto)
    monkeypatch.setattr(metrics, "PDFReportsCounter", pdf)
    monkeypatch.setattr(metrics, "SimulationRunsCounter", simulation)

    metrics.increment_crypto_operation("ChaCha20-Poly1305")
    metrics.increment_pdf_report("audit")
    metrics.increment_simulation_run("agent-9")

    crypto.labels.assert_called_once_with(algorithm="ChaCha20-Poly1305")
    pdf.labels.assert_called_once_with(type="audit")
    simulation.labels.assert_called_once_with(agent_id="agent-9")


def test_workflow_latency_observation_delegates_exact_value(monkeypatch) -> None:
    histogram = Mock()
    monkeypatch.setattr(metrics, "WorkflowLatencyHistogram", histogram)

    metrics.observe_workflow_latency(1.25)

    histogram.observe.assert_called_once_with(1.25)


def test_noop_metrics_support_labels_increment_and_observe() -> None:
    counter = metrics._NoopCounter()
    histogram = metrics._NoopHistogram()

    assert counter.labels(rank="x") is counter
    assert counter.inc() is None
    assert counter.inc(3.5) is None
    assert histogram.observe(2.0) is None
