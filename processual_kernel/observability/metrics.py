from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram

    CGTEvaluationsCounter = Counter("processual_cgt_evaluations_total", "Total CGT evaluations")
    FateRankCounter = Counter("processual_fate_rank_total", "Fate rank distribution", ["rank"])
    WorkflowCheckpointsCounter = Counter("processual_workflow_checkpoints_total", "Total workflow checkpoints")
    GovernanceActionsCounter = Counter("processual_governance_actions_total", "Governance actions", ["action"])
    DiscordAlertsCounter = Counter("processual_discord_alerts_total", "Discord alerts sent")
    CryptoOperationsCounter = Counter("processual_crypto_operations_total", "Crypto operations", ["algorithm"])
    CryptoFailuresCounter = Counter("processual_crypto_failures_total", "Crypto operation failures")
    WorkflowLatencyHistogram = Histogram("processual_workflow_latency_seconds", "Workflow latency")
    PDFReportsCounter = Counter("processual_pdf_reports_total", "PDF reports generated", ["type"])
    SimulationRunsCounter = Counter("processual_simulation_runs_total", "Simulation runs", ["agent_id"])
    TelemetryIngestedCounter = Counter("processual_telemetry_ingested_total", "Telemetry points ingested")

    _prometheus_available = True
except Exception:
    _prometheus_available = False

    class _NoopCounter:
        def labels(self, **kwargs) -> _NoopCounter:
            return self

        def inc(self, amount: float = 1.0) -> None:
            pass

    class _NoopHistogram:
        def observe(self, amount: float) -> None:
            pass

    CGTEvaluationsCounter = _NoopCounter()
    FateRankCounter = _NoopCounter()
    WorkflowCheckpointsCounter = _NoopCounter()
    GovernanceActionsCounter = _NoopCounter()
    DiscordAlertsCounter = _NoopCounter()
    CryptoOperationsCounter = _NoopCounter()
    CryptoFailuresCounter = _NoopCounter()
    WorkflowLatencyHistogram = _NoopHistogram()
    PDFReportsCounter = _NoopCounter()
    SimulationRunsCounter = _NoopCounter()
    TelemetryIngestedCounter = _NoopCounter()


def increment_cgt_evaluations() -> None:
    CGTEvaluationsCounter.inc()


def increment_fate_rank(rank: str) -> None:
    FateRankCounter.labels(rank=rank).inc()


def increment_workflow_checkpoint() -> None:
    WorkflowCheckpointsCounter.inc()


def increment_governance_action(action: str) -> None:
    GovernanceActionsCounter.labels(action=action).inc()


def increment_discord_alert() -> None:
    DiscordAlertsCounter.inc()


def increment_crypto_operation(algorithm: str = "AES-256-GCM") -> None:
    CryptoOperationsCounter.labels(algorithm=algorithm).inc()


def increment_crypto_failure() -> None:
    CryptoFailuresCounter.inc()


def observe_workflow_latency(seconds: float) -> None:
    WorkflowLatencyHistogram.observe(seconds)


def increment_pdf_report(type_: str = "governance") -> None:
    PDFReportsCounter.labels(type=type_).inc()


def increment_simulation_run(agent_id: str = "unknown") -> None:
    SimulationRunsCounter.labels(agent_id=agent_id).inc()


def increment_telemetry_ingested(count: int = 1) -> None:
    TelemetryIngestedCounter.inc(count)
