from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from benchmarks.orchestration_api_app import app
from benchmarks.orchestration_api_probe import classify_response, percentile


def test_classify_response_distinguishes_capacity_backpressure() -> None:
    assert classify_response(httpx.Response(200)) == "success"
    assert (
        classify_response(
            httpx.Response(
                429,
                headers={"X-Maestro-Capacity-Reason": "execution_fanout"},
            )
        )
        == "backpressure"
    )
    assert classify_response(httpx.Response(429)) == "error"
    assert classify_response(httpx.Response(503)) == "error"


def test_percentile_uses_nearest_rank() -> None:
    assert percentile([], 0.95) == 0.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.50) == 2.0
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_real_orchestration_router_benchmark_smoke(monkeypatch) -> None:
    monkeypatch.setenv("EXECUTION_FANOUT_ENABLED", "false")
    client = TestClient(app)

    response = client.post(
        "/workflows/llm-orchestration",
        json={
            "provider": "benchmark-orchestration",
            "prompts": [f"prompt-{index}" for index in range(12)],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["width"] == 12
    assert payload["paced"] is True
    assert payload["local_parallelism"] == 2
    assert payload["plan_reason"] == "broad_single_provider"
    assert len(payload["results"]) == 12
    assert all(item["status"] == "success" for item in payload["results"])

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "maestro_llm_orchestration_requests_total" in metrics.text
    assert 'plan_reason="broad_single_provider"' in metrics.text
