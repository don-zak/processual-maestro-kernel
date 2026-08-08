from __future__ import annotations

import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.cgt_governor.adapters.base import BaseLLMAdapter
from processual_api.cgt_governor.adapters.execution_fanout import (
    ExecutionFanoutSaturatedError,
)
from processual_api.cgt_governor.policy import orchestration_metrics
from processual_api.main import metrics_endpoint
from processual_api.routers import workflows


class HTTPMetricsAdapter(BaseLLMAdapter):
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        del system_prompt, kwargs
        return f"response:{prompt}"

    def is_configured(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "http-metrics"


def _metric_value(text: str, metric: str, labels: dict[str, str]) -> float:
    required = [f'{key}="{value}"' for key, value in labels.items()]
    for line in text.splitlines():
        if not line.startswith(metric + "{"):
            continue
        if all(label in line for label in required):
            match = re.search(r"\}\s+([0-9.eE+-]+)$", line)
            if match is None:
                raise AssertionError(f"cannot parse metric line: {line}")
            return float(match.group(1))
    return 0.0


def _client(monkeypatch) -> TestClient:
    adapter = HTTPMetricsAdapter()
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    app = FastAPI()
    app.include_router(workflows.router)
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
    app.dependency_overrides[workflows.get_current_user] = lambda: "metrics-test-user"
    return TestClient(app)


def test_http_orchestration_is_exposed_through_metrics(monkeypatch) -> None:
    client = _client(monkeypatch)

    labels = {
        "paced": "true",
        "plan_reason": "broad_single_provider",
        "outcome": "success",
    }
    before = client.get("/metrics")
    assert before.status_code == 200
    before_requests = _metric_value(
        before.text,
        "maestro_llm_orchestration_requests_total",
        labels,
    )

    response = client.post(
        "/workflows/llm-orchestration",
        json={
            "provider": "http-metrics",
            "prompts": [f"prompt-{index}" for index in range(12)],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["paced"] is True
    assert payload["local_parallelism"] == 2
    assert payload["plan_reason"] == "broad_single_provider"

    after = client.get("/metrics")
    assert after.status_code == 200
    after_requests = _metric_value(
        after.text,
        "maestro_llm_orchestration_requests_total",
        labels,
    )
    assert after_requests == before_requests + 1.0

    width_labels = {
        "paced": "true",
        "plan_reason": "broad_single_provider",
    }
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_width_count",
        width_labels,
    ) >= 1.0
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_width_sum",
        width_labels,
    ) >= 12.0
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_latency_seconds_count",
        labels,
    ) >= 1.0

    item_labels = {
        "paced": "true",
        "plan_reason": "broad_single_provider",
        "outcome": "success",
    }
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_item_outcomes_total",
        item_labels,
    ) >= 12.0


def test_http_saturation_is_exposed_through_metrics(monkeypatch) -> None:
    client = _client(monkeypatch)

    async def saturated_executor(items, worker, plan):
        del worker, plan
        return [ExecutionFanoutSaturatedError("provider") for _item in items]

    monkeypatch.setattr(workflows, "execute_fanout_plan", saturated_executor)

    request_labels = {
        "paced": "false",
        "plan_reason": "shared_governor_only",
        "outcome": "saturated",
    }
    error_labels = {
        "paced": "false",
        "plan_reason": "shared_governor_only",
        "outcome": "error",
    }
    before = client.get("/metrics")
    before_requests = _metric_value(
        before.text,
        "maestro_llm_orchestration_requests_total",
        request_labels,
    )
    before_errors = _metric_value(
        before.text,
        "maestro_llm_orchestration_item_outcomes_total",
        error_labels,
    )

    response = client.post(
        "/workflows/llm-orchestration",
        json={
            "provider": "http-metrics",
            "prompts": ["prompt-0", "prompt-1"],
        },
    )

    assert response.status_code == 429
    assert response.headers["X-Maestro-Capacity-Reason"] == "execution_fanout"

    after = client.get("/metrics")
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_requests_total",
        request_labels,
    ) == before_requests + 1.0
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_item_outcomes_total",
        error_labels,
    ) == before_errors + 2.0
    assert _metric_value(
        after.text,
        "maestro_llm_orchestration_latency_seconds_count",
        request_labels,
    ) >= 1.0


def test_http_orchestration_succeeds_when_metrics_collector_breaks(monkeypatch) -> None:
    client = _client(monkeypatch)

    class BrokenCounter:
        def labels(self, **_labels):
            raise RuntimeError("metrics backend unavailable")

    monkeypatch.setattr(orchestration_metrics, "_PROMETHEUS_AVAILABLE", True)
    monkeypatch.setattr(orchestration_metrics, "ORCHESTRATION_REQUESTS", BrokenCounter())

    response = client.post(
        "/workflows/llm-orchestration",
        json={
            "provider": "http-metrics",
            "prompts": ["prompt-0", "prompt-1", "prompt-2", "prompt-3"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["width"] == 4
    assert all(item["status"] == "success" for item in payload["results"])
