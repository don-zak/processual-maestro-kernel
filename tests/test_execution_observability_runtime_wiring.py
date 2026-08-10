from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from processual_api.cgt_governor.adapters.base import BaseLLMAdapter
from processual_api.cgt_governor.adapters.execution_fanout import ExecutionFanoutSaturatedError
from processual_api.main import app
from processual_api.routers import execution_observability, workflows
from processual_api.services.execution_observability import (
    clear_execution_observations_for_tests,
    execution_observability_snapshot,
    record_execution_observation,
)


class ExecutionObservabilityAdapter(BaseLLMAdapter):
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        del system_prompt, kwargs
        return f"observed:{prompt}"

    def is_configured(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "execution-observability"


def setup_function() -> None:
    clear_execution_observations_for_tests()


def teardown_function() -> None:
    clear_execution_observations_for_tests()


def _client(monkeypatch) -> TestClient:
    adapter = ExecutionObservabilityAdapter()
    monkeypatch.setattr(workflows.adapter_registry, "get", lambda provider: adapter)

    test_app = FastAPI()
    test_app.include_router(workflows.router)
    test_app.dependency_overrides[workflows.get_current_user] = lambda: "observability-test-user"
    return TestClient(test_app)


def _settings_client(user: dict[str, object]) -> TestClient:
    test_app = FastAPI()
    test_app.include_router(execution_observability.router)
    test_app.dependency_overrides[execution_observability.get_current_user] = lambda: user
    return TestClient(test_app)


def test_execution_observability_summary_route_is_registered_once() -> None:
    paths = [route.path for route in app.routes]
    assert paths.count("/settings/execution-observability/summary") == 1


def test_execution_observability_summary_requires_usage_read_scope() -> None:
    record_execution_observation(
        execution_kind="task",
        task_id="task.secure",
        status="success",
        duration_ms=1,
        items_total=1,
        items_succeeded=1,
    )

    denied = _settings_client({"sub": "reviewer"}).get(
        "/settings/execution-observability/summary"
    )
    assert denied.status_code == 403
    assert "admin:usage:read" in denied.json()["detail"]

    allowed = _settings_client(
        {
            "sub": "reviewer",
            "supervision_scopes": ["admin:usage:read"],
        }
    ).get("/settings/execution-observability/summary")
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["source_of_truth"] == "canonical_execution_records"
    assert payload["summary"]["executions_total"] == 1
    assert payload["recent_executions"][0]["task_id"] == "task.secure"


def test_llm_orchestration_records_canonical_execution_and_returns_id(monkeypatch) -> None:
    client = _client(monkeypatch)

    response = client.post(
        "/workflows/llm-orchestration",
        json={
            "provider": "execution-observability",
            "prompts": ["one", "two", "three"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_id"].startswith("exec_")

    snapshot = execution_observability_snapshot(limit=10)
    assert snapshot["record_count"] == 1
    assert snapshot["summary"]["executions_succeeded"] == 1
    assert snapshot["summary"]["items_total"] == 3
    assert snapshot["summary"]["items_succeeded"] == 3
    assert snapshot["by_task"] == {"workflow.llm_orchestration": 1}
    assert snapshot["by_provider"] == {"execution-observability": 1}
    recent = snapshot["recent_executions"][0]
    assert recent["execution_id"] == payload["execution_id"]
    assert recent["status"] == "success"
    assert recent["items_succeeded"] == 3


def test_llm_orchestration_saturation_records_failure_evidence(monkeypatch) -> None:
    client = _client(monkeypatch)

    async def saturated_executor(items, worker, plan):
        del worker, plan
        return [ExecutionFanoutSaturatedError("provider") for _item in items]

    monkeypatch.setattr(workflows, "execute_fanout_plan", saturated_executor)

    response = client.post(
        "/workflows/llm-orchestration",
        json={
            "provider": "execution-observability",
            "prompts": ["one", "two"],
        },
    )

    assert response.status_code == 429
    snapshot = execution_observability_snapshot(limit=10)
    assert snapshot["record_count"] == 1
    assert snapshot["summary"]["executions_failed"] == 1
    assert snapshot["summary"]["items_failed"] == 2
    recent = snapshot["recent_executions"][0]
    assert recent["status"] == "saturated"
    assert recent["failure_stage"] == "execution"
    assert recent["failure_code"] == "execution_fanout_saturated"
