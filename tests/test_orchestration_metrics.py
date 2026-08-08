from __future__ import annotations

from processual_api.cgt_governor.policy import orchestration_metrics


def test_metric_labels_are_bounded() -> None:
    assert orchestration_metrics._bounded_reason("broad_single_provider") == "broad_single_provider"
    assert orchestration_metrics._bounded_reason("provider-secret-name") == "unknown"
    assert orchestration_metrics._bounded_outcome("success") == "success"
    assert orchestration_metrics._bounded_outcome("provider-specific-error") == "unknown"


def test_record_orchestration_is_safe_without_prometheus(monkeypatch) -> None:
    monkeypatch.setattr(orchestration_metrics, "_PROMETHEUS_AVAILABLE", False)

    orchestration_metrics.record_orchestration(
        orchestration_metrics.OrchestrationObservation(
            paced=True,
            plan_reason="broad_single_provider",
            width=16,
            outcome="success",
            latency_seconds=1.25,
            success_items=16,
            error_items=0,
        )
    )
